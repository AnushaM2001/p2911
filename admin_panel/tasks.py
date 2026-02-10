from celery import shared_task
import requests
from admin_panel.models import Order, Notification
from django.utils import timezone
import time

# admin_panel/tasks.py
from admin_panel.Notifications import notify_admins

import logging
from decimal import Decimal
from celery import shared_task, chain
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
from django.contrib.auth import get_user_model
from admin_panel.models import Order
from admin_panel.utils import create_shiprocket_order, assign_awb, send_invoice_email,get_shiprocket_token, send_push_notification
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
    orders = Order.objects.filter(
        status="Completed",
        shiprocket_shipment_id__isnull=True,
        order_ref__isnull=False   # ✅ VERY IMPORTANT
    )

    for order in orders:
        process_order_with_shiprocket.delay(order.id)

@shared_task
def schedule_awb_fetch():
    orders = Order.objects.filter(
        shiprocket_shipment_id__isnull=False,
        shiprocket_awb_code__isnull=True
    )

    for order in orders:
        fetch_shiprocket_awb_task.delay(order.id)



# Step 1: Create Shiprocket Order
@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def create_shiprocket_order_task(self, order_id):
    try:
        order = Order.objects.filter(
           id=order_id,
             status="Completed",
            shiprocket_order_id__isnull=True
                 ).first()

        if not order:
            return None


        if not order.address:
            return {"error": "Address missing"}

        response = create_shiprocket_order(
            order,
            order.address,
            order.items.all()
        )

        if response.get("status") != "success":
            raise Exception(response)

        shiprocket_data = response.get("shiprocket", {})

        order.shiprocket_order_id = shiprocket_data.get("order_id")
        order.shiprocket_shipment_id = shiprocket_data.get("shipment_id")

        safe_save(order, update_fields=[
            "shiprocket_order_id",
            "shiprocket_shipment_id",
        ])

        notify_admins(
            f"📦 Shiprocket order created\nOrder #{order.id}",
            category="orders"
        )

        return order.id

    except Exception as exc:
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"error": f"Shiprocket create failed for {order_id}"}


# Step 2: Assign AWB asynchronously
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import re
@shared_task(bind=True)
def send_invoice_email_task(self, order_id):
    order = Order.objects.get(id=order_id)

    if order.invoice_sent:
        return "Invoice already sent"

    if not order.shiprocket_order_id or not order.shiprocket_awb_code:
        logger.info(f"Order {order.id} not ready for invoice")
        return

    email = getattr(order.address, "email", None)
    if not email:
        raise Exception("Customer email missing")

    send_invoice_email(email=email, order=order)

    order.invoice_sent = True
    order.save(update_fields=["invoice_sent"])

    return "Invoice sent"

@shared_task(bind=True, max_retries=10, default_retry_delay=120)
def fetch_shiprocket_awb_task(self, order_id):

    if not isinstance(order_id, int):
        return {"info": "Invalid order id, skipping AWB fetch"}

    try:
        order = Order.objects.filter(
            id=order_id,
            shiprocket_shipment_id__isnull=False,
            shiprocket_awb_code__isnull=True
        ).first()

        if not order:
            return {"info": f"Order {order_id} not eligible for AWB fetch"}

        token = get_shiprocket_token()
        headers = {"Authorization": f"Bearer {token}"}

        url = f"https://apiv2.shiprocket.in/v1/external/shipments/{order.shiprocket_shipment_id}"
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 404:
            return {"error": f"Shipment not found for order {order_id}"}

        if response.status_code != 200:
            raise Exception(f"Shipment fetch failed: {response.text}")

        data = response.json().get("data", {})
        awb = data.get("awb")
        courier = data.get("courier_name")

        if not awb:
            raise Exception("AWB not generated yet")

        order.shiprocket_awb_code = awb
        order.shiprocket_courier_name = courier
        order.status = "awb_assigned"

        safe_save(order, update_fields=[
            "shiprocket_awb_code",
            "shiprocket_courier_name",
            "status"
        ])

        notify_admins(
            f"✅ AWB auto-assigned\nOrder #{order.id}\nAWB: {awb}",
            category="orders"
        )
        # ✅ NOW trigger invoice (THIS IS THE KEY)
        send_invoice_email_task.delay(order.id)

        return {"success": True}

    except Exception as exc:
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"error": f"AWB fetch failed permanently for order {order_id}"}
import requests
from django.conf import settings
from celery import shared_task
from .models import Order
from .utils import get_shiprocket_token   # or wherever your token function is

@shared_task(bind=True, max_retries=3)
def generate_shiprocket_pickup_task(self, order_id):
    try:
        order = Order.objects.get(id=order_id, shiprocket_shipment_id__isnull=False)

        token = get_shiprocket_token()
        url = "https://apiv2.shiprocket.in/v1/external/courier/generate/pickup"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {"shipment_id": order.shiprocket_shipment_id}

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if response.status_code == 200:
            order.shiprocket_pickup_generated = True
            order.save(update_fields=["shiprocket_pickup_generated"])
            return "Pickup generated"

        raise Exception(data)

    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)

# Helper function to run the full chain
@shared_task
def process_order_with_shiprocket(order_id):
    """Create order and assign AWB using Celery chain."""
    workflow = chain(
        create_shiprocket_order_task.s(order_id),
        # fetch_shiprocket_awb_task.s(),
        # generate_shiprocket_pickup_task.s()
    )
    workflow.apply_async()


from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import logging

logger = logging.getLogger(__name__)



@shared_task
def send_pending_invoices():
    orders = Order.objects.filter(
        invoice_sent=False,
        shiprocket_order_id__isnull=False,
        shiprocket_awb_code__isnull=False
    )

    for order in orders:
        send_invoice_email_task.delay(order.id)



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
                Notification.objects.create(
                message=msg,
                user=order.user if order.user_id else None
                 )


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

