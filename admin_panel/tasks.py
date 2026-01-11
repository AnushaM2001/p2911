from celery import shared_task
import requests
from admin_panel.models import Order, Notification
from admin_panel.utils import get_shiprocket_token, send_push_notification
from django.utils import timezone
import time

# admin_panel/tasks.py

import logging
from decimal import Decimal
from celery import shared_task, chain
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
from django.contrib.auth import get_user_model
from admin_panel.models import Order
from .utils import create_shiprocket_order, assign_awb, notify_admins, send_invoice_email
from django.db import transaction, OperationalError
# from admin_panel.utils import get_guest_id

logger = logging.getLogger(__name__)


def safe_save(instance, update_fields=None, max_retries=5, delay=1):
    """Save instance safely with retries to avoid database locks."""
    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                instance.save(update_fields=update_fields)
            return True
        except OperationalError as e:
            if "locked" in str(e).lower():
                time.sleep(delay)
            else:
               raise
    raise OperationalError(f"Could not save {instance} after {max_retries} attempts")
@shared_task
def schedule_pending_shiprocket_orders():
    pending_orders = Order.objects.filter(
        status="Completed",
        shiprocket_order_id__isnull=True
    )

    for order in pending_orders:
        process_order_with_shiprocket.delay(order.id)


# Step 1: Create Shiprocket Order
@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def create_shiprocket_order_task(self, order_id):
    try:
        order = Order.objects.get(id=order_id, status="Completed", shiprocket_order_id__isnull=True)
        if not order.address:
            return {"error": f"No address linked for order {order_id}"}

        shiprocket_response = create_shiprocket_order(order, order.address, order.items.all())
        if shiprocket_response.get("status") != "success":
            raise Exception(f"Shiprocket API error: {shiprocket_response}")

        shiprocket_order_id = shiprocket_response.get("shiprocket_response", {}).get("order_id")
        if not shiprocket_order_id:
            # fallback from awb_response
            shiprocket_order_id = shiprocket_response.get("awb_response", {}).get("response", {}).get("data", {}).get("order_id")
            if not shiprocket_order_id:
                raise Exception(f"No order_id returned by Shiprocket: {shiprocket_response}")

        order.shiprocket_order_id = shiprocket_order_id
        safe_save(order, update_fields=["shiprocket_order_id"])

        return order.id  # Pass order ID to next task in the chain

    except Exception as exc:
        try:
            self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            return {"error": f"Order creation failed for {order_id}: {exc}"}


# Step 2: Assign AWB asynchronously
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import re

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def assign_shiprocket_awb_task(self, order_id):
    try:
        order = Order.objects.get(
            id=order_id,
            shiprocket_shipment_id__isnull=False
        )

        awb_response = assign_awb(order.shiprocket_shipment_id)

        awb_code = None
        courier_name = None
        courier_id = None

        # -------------------------------
        # CASE 1️⃣ Normal success response
        # -------------------------------
        if isinstance(awb_response, dict):
            awb_code = (
                awb_response
                .get("response", {})
                .get("data", {})
                .get("awb_code")
            )

            courier_name = (
                awb_response
                .get("response", {})
                .get("data", {})
                .get("courier_name")
            )

            courier_id = (
                awb_response
                .get("response", {})
                .get("data", {})
                .get("courier_company_id")
            )

        # ------------------------------------
        # CASE 2️⃣ AWB already assigned (500)
        # ------------------------------------
        if not awb_code:
            message = awb_response.get("message", "") if isinstance(awb_response, dict) else ""

            if "AWB is already assigned" in message:
                match = re.search(r"awb\s*-\s*(\w+)", message)
                if match:
                    awb_code = match.group(1)

        # ------------------------------------
        # FINAL VALIDATION
        # ------------------------------------
        if not awb_code:
            raise Exception("AWB still not available")

        # ✅ SAVE ONCE AND EXIT
        order.shiprocket_awb_code = awb_code
        order.shiprocket_courier_name = courier_name
        order.shiprocket_courier_id = courier_id
        order.status = "awb_assigned"

        safe_save(order, update_fields=[
            "shiprocket_awb_code",
            "shiprocket_courier_name",
            "shiprocket_courier_id",
            "status"
        ])

        print(f"✅ AWB CONFIRMED → Order #{order.id}: {awb_code}")

        return {
            "success": True,
            "order_id": order.id,
            "awb_code": awb_code
        }

    except Exception as exc:
        print("⚠️ AWB assignment retry:", exc)
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {
                "error": f"AWB assignment failed permanently for order {order_id}",
                "reason": str(exc)
            }


# Helper function to run the full chain
@shared_task
def process_order_with_shiprocket(order_id):
    """Create order and assign AWB using Celery chain."""
    workflow = chain(
        create_shiprocket_order_task.s(order_id),
        assign_shiprocket_awb_task.s()
    )
    workflow.apply_async()

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_invoice_email_task(self, order_id=None):
    """
    Send invoice emails for guest orders.
    - Sends only once (invoice_sent=False)
    - Uses email from AddressModel
    - Retries automatically on failure
    """

    try:
        orders = Order.objects.filter(
            invoice_sent=False,
            shiprocket_awb_code__isnull=False
        ).exclude(shiprocket_awb_code="")

        if order_id:
            orders = orders.filter(id=order_id)

        results = []

        for order in orders:
            try:
                # ✅ Get email from address
                email = None
                if order.address and getattr(order.address, "email", None):
                    email = order.address.email

                if not email:
                    logger.warning(f"No email found for order {order.id}")
                    continue

                # ✅ Send invoice
                send_invoice_email(email=email, order=order)

                # ✅ Mark as sent
                order.invoice_sent = True
                safe_save(order, update_fields=["invoice_sent"])

                results.append({"success": f"Invoice sent for order {order.id}"})

            except Exception as inner_e:
                logger.exception(f"Failed to send invoice for order {order.id}, retrying...")
                try:
                    self.retry(exc=inner_e, countdown=60)
                except MaxRetriesExceededError:
                    results.append({
                        "error": f"Invoice failed permanently for order {order.id}: {inner_e}"
                    })

        return results or {"info": "No invoices pending"}

    except Exception as e:
        logger.exception("Invoice task crashed")
        try:
            self.retry(exc=e, countdown=60)
        except MaxRetriesExceededError:
            return {"error": str(e)}



@shared_task
def notify_low_stock_task(order_id=None):
    """
    Notify admins if stock is low (<= 5).
    - If order_id given → check only that order.
    - Else → check last 50 recent orders.
    """
    try:
        orders = Order.objects.order_by("-created_at")[:50] if not order_id else Order.objects.filter(id=order_id)
        results = []

        for order in orders:
            for item in order.items.all():
                try:
                    if item.product_variant and item.product_variant.stock <= 5:
                        notify_admins(f"⚠️ Low stock: {item.product_variant}", category="stocks")
                    elif item.gift_set and item.gift_set.stock <= 5:
                        notify_admins(f"⚠️ Low stock: {item.gift_set}", category="stocks")
                    elif item.product and item.product.stock <= 5:
                        notify_admins(f"⚠️ Low stock: {item.product}", category="stocks")
                except Exception as inner_e:
                    logger.warning(f"Stock check failed for order {order.id}: {inner_e}")

            results.append({"checked": f"Order {order.id}"})

        return results or {"info": "No stock issues found"}

    except Exception as e:
        logger.exception("Low stock task failed")
        return {"error": str(e)}



@shared_task
def fetch_tracking_status():
    """
    Periodically fetch Shiprocket tracking updates.
    - Updates status only when changed
    - Handles MISROUTED shipments (admin alert, no retries)
    - Skips delivered / cancelled orders
    """

    # 🔍 Only active shipments
    active_orders = Order.objects.filter(
        shiprocket_awb_code__isnull=False
    ).exclude(
        shiprocket_awb_code=''
    ).exclude(
        shiprocket_tracking_status__in=[
            "Delivered",
            "RTO Delivered",
            "Cancelled"
        ]
    )

    if not active_orders.exists():
        print("ℹ️ No active orders to track")
        return

    token = get_shiprocket_token()
    headers = {"Authorization": f"Bearer {token}"}

    for order in active_orders:
        try:
            url = f"https://apiv2.shiprocket.in/v1/external/courier/track/awb/{order.shiprocket_awb_code}"
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                print(
                    f"❌ Order #{order.id} tracking failed "
                    f"[{response.status_code}] {response.text}"
                )
                continue

            data = response.json()
            tracking_data = data.get("tracking_data", {})
            shipment_tracks = tracking_data.get("shipment_track", [])

            # 🔁 Normalize response
            if isinstance(shipment_tracks, dict):
                shipment_tracks = [shipment_tracks]
            elif not isinstance(shipment_tracks, list):
                shipment_tracks = []

            if not shipment_tracks:
                print(f"⚠️ Order #{order.id} has no tracking events")
                continue

            latest_track = shipment_tracks[-1]
            current_status = latest_track.get("current_status", "").strip()
            etd = tracking_data.get("etd", "")

            if not current_status:
                continue

            # 🚨 MISROUTED HANDLING (ONE-TIME)
            if current_status == "MISROUTED":
                if not getattr(order, "shiprocket_issue_flag", False):
                    with transaction.atomic():
                        order.shiprocket_issue_flag = True
                        order.shiprocket_issue_reason = "MISROUTED"
                        order.shiprocket_tracking_status = current_status
                        order.shiprocket_tracking_info = tracking_data
                        order.shiprocket_tracking_events = shipment_tracks
                        order.shiprocket_tracking_status_updated_at = timezone.now()
                        order.save(update_fields=[
                            "shiprocket_issue_flag",
                            "shiprocket_issue_reason",
                            "shiprocket_tracking_status",
                            "shiprocket_tracking_info",
                            "shiprocket_tracking_events",
                            "shiprocket_tracking_status_updated_at"
                        ])

                    notify_admins(
                        f"⚠️ MISROUTED shipment detected\n"
                        f"Order #{order.id}\n"
                        f"AWB: {order.shiprocket_awb_code}",
                        category="shiprocket"
                    )

                    print(f"🚨 Order #{order.id} marked MISROUTED")

                # ⛔ Stop further processing for this order
                continue

            # ✅ Normal status update (only if changed)
            if current_status != order.shiprocket_tracking_status:
                with transaction.atomic():
                    order.shiprocket_tracking_status = current_status
                    order.shiprocket_tracking_info = tracking_data
                    order.shiprocket_estimated_delivery = etd
                    order.shiprocket_tracking_events = shipment_tracks
                    order.shiprocket_tracking_status_updated_at = timezone.now()
                    order.save(update_fields=[
                        "shiprocket_tracking_status",
                        "shiprocket_tracking_info",
                        "shiprocket_estimated_delivery",
                        "shiprocket_tracking_events",
                        "shiprocket_tracking_status_updated_at"
                    ])

                msg = f"📦 Order #{order.id} is now '{current_status}'"
                Notification.objects.create(message=msg)

                send_push_notification(
                    guest_id=order.guest_id,
                    title="Order Update",
                    message=msg
                )

                print(f"✅ Order #{order.id} updated → {current_status}")

            else:
                print(f"ℹ️ Order #{order.id} already up-to-date ({current_status})")

        except Exception as e:
            print(f"⚠️ Tracking error for Order #{order.id}: {e}")

