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


logger = logging.getLogger(__name__)


def safe_save(instance, update_fields=None, max_retries=5, delay=1):
    """Save instance safely with retries to avoid database locks."""
    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                instance.save(update_fields=update_fields)
            return True
        except OperationalError as e:
            if "database is locked" in str(e):
                time.sleep(delay)
            else:
                raise
    raise OperationalError(f"Could not save {instance} after {max_retries} attempts")


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
@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def assign_shiprocket_awb_task(self, order_id):
    try:
        order = Order.objects.get(id=order_id, shiprocket_order_id__isnull=False)
        max_attempts = 10
        awb_code = None

        for attempt in range(max_attempts):
            awb_response = assign_awb(order.shiprocket_order_id, order.shiprocket_courier_id)
            awb_code = awb_response.get("response", {}).get("data", {}).get("awb_code")
            if awb_code:
                break
            time.sleep(5)  # wait 5 seconds before retry

        if not awb_code:
            raise Exception(f"AWB not generated yet for order {order_id}")

        order.shiprocket_awb_code = awb_code
        order.shiprocket_courier_id = awb_response.get("response", {}).get("data", {}).get("courier_company_id")
        order.shiprocket_courier_name = awb_response.get("response", {}).get("data", {}).get("courier_name")
        order.status = "awb_assigned"

        safe_save(order, update_fields=[
            "shiprocket_awb_code",
            "shiprocket_courier_id",
            "shiprocket_courier_name",
            "status"
        ])

        return {"success": f"AWB assigned for order {order_id}"}

    except Exception as exc:
        try:
            self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            return {"error": f"AWB assignment failed for order {order_id}: {exc}"}


# Helper function to run the full chain
@shared_task
def process_order_with_shiprocket(order_id):
    """Create order and assign AWB using Celery chain."""
    workflow = chain(
        create_shiprocket_order_task.s(order_id),
        assign_shiprocket_awb_task.s()
    )
    workflow.apply_async()

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_invoice_email_task(self, user_id=None, order_id=None):
    """
    Send invoice emails only once.
    - If user_id + order_id provided → send for that order.
    - Else → send for all completed orders without invoice_sent=True.
    - Retries automatically if sending fails.
    """
    User = get_user_model()
    try:
        orders = Order.objects.filter(shiprocket_awb_code__isnull=False).exclude(shiprocket_awb_code="").filter(invoice_sent=False)
     
        if user_id and order_id:
            orders = orders.filter(id=order_id, user_id=user_id)

        results = []
        for order in orders:
            try:
                send_invoice_email(order.user, order)
                order.invoice_sent = True
                order.save(update_fields=["invoice_sent"])
                results.append({"success": f"Invoice sent for order {order.id}"})
            except Exception as inner_e:
                logger.exception(f"Failed to send invoice for order {order.id}, retrying...")
                try:
                    self.retry(exc=inner_e, countdown=60)
                except MaxRetriesExceededError:
                    results.append({"error": f"Invoice failed for order {order.id} after retries: {inner_e}"})

        return results or {"info": "No invoices to send"}

    except Exception as e:
        logger.exception("Invoice task failed")
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
    from django.db import transaction

    # ✅ Filter only orders that are in transit / not delivered
    active_orders = Order.objects.filter(
        shiprocket_awb_code__isnull=False
    ).exclude(shiprocket_awb_code='').exclude(
        shiprocket_tracking_status__in=["Delivered", "RTO Delivered", "Cancelled"]
    )

    if not active_orders.exists():
        print("ℹ️ No active orders to track")
        return

    token = get_shiprocket_token()
    headers = {"Authorization": f"Bearer {token}"}

    for order in active_orders:
        try:
            url = f"https://apiv2.shiprocket.in/v1/external/courier/track/awb/{order.shiprocket_awb_code}"
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                tracking_data = data.get("tracking_data", {})
                shipment_tracks = tracking_data.get("shipment_track", [])

                # Normalize response
                if isinstance(shipment_tracks, dict):
                    shipment_tracks = [shipment_tracks]
                elif not isinstance(shipment_tracks, list):
                    shipment_tracks = []

                if not shipment_tracks:
                    print(f"⚠️ No shipment_track data for Order #{order.id}")
                    continue

                latest_track = shipment_tracks[-1]
                current_status = latest_track.get("current_status", "")
                etd = tracking_data.get("etd", "")

                # ✅ Save only if new status
                if current_status and current_status != order.shiprocket_tracking_status:
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

                    # 🔔 Notify customer/admins
                    msg = f"📦 Order #{order.id} is now '{current_status}'"
                    Notification.objects.create(message=msg)
                    send_push_notification(order.user, msg)

                    print(f"✅ Order #{order.id} updated → {current_status}")
                else:
                    print(f"ℹ️ Order #{order.id} already up-to-date: {current_status}")

            elif response.status_code == 500:
                error_msg = response.json().get("message", "Unknown error")
                print(f"❌ Order #{order.id} - AWB may be cancelled: {error_msg}")
            else:
                print(f"❌ Order #{order.id} error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"⚠️ Error tracking Order #{order.id}: {e}")

