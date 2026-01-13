from celery import uuid
import requests
from admin_panel.models import *
from django.conf import settings
from user_panel.models import *
import datetime
import json

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile


def compress_image(image_field, quality=70):
    """
    Compress and convert an image to WebP.
    Preserves transparency for PNGs.
    """
    if not image_field:
        return image_field

    img = Image.open(image_field)
    img_io = BytesIO()

    # Preserve transparency for PNGs
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    # Save as WebP
    img.save(img_io, format="WEBP", quality=quality, optimize=True)

    # Change file name extension to .webp
    name = image_field.name.rsplit('.', 1)[0] + ".webp"
    return ContentFile(img_io.getvalue(), name=name)

       # password from your email

def get_shiprocket_token():
    # Check if existing token is still valid
    token_obj = ShiprocketToken.objects.order_by('-created_at').first()
    if token_obj and token_obj.is_valid():
        return token_obj.token

    # Else, get new token from API
    url = "https://apiv2.shiprocket.in/v1/external/auth/login"
    payload = {
        "email": settings.SHIPROCKET_EMAIL,
        "password": settings.SHIPROCKET_PASSWORD
    }
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        token = response.json().get("token")
        if token:
            ShiprocketToken.objects.create(token=token)
            return token
        else:
            raise Exception("Token missing in response")
    else:
        raise Exception(f"Shiprocket login failed: {response.text}")

import datetime
import requests
import json


# =====================================================
# 📍 SERVICEABILITY CHECK (ADDRESS ONLY)
# =====================================================

def check_shiprocket_service(address, declared_value=1000):
    """
    ✅ Only checks if address is serviceable
    ❌ No courier selection
    ❌ No freight / ETD logic
    """

    if not address:
        return {"error": "Address missing"}

    token = get_shiprocket_token()
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        # ⚠️ MUST MATCH PICKUP LOCATION PINCODE IN SHIPROCKET PANEL
        "pickup_postcode": "500008",
        "delivery_postcode": address.Pincode,
        "cod": 0,                 # PREPAID
        "weight": 1.0,            # FIXED SAFE WEIGHT
        "order_type": 1,
        "declared_value": declared_value
    }

    response = requests.get(
        "https://apiv2.shiprocket.in/v1/external/courier/serviceability/",
        headers=headers,
        params=params,
        timeout=10
    )

    data = response.json()
    couriers = data.get("data", {}).get("available_courier_companies", [])

    if not couriers:
        return {"error": "Address not serviceable"}

    return {"serviceable": True}


# =====================================================
# 🧾 ADDRESS VALIDATION
# =====================================================

def validate_address_for_shiprocket(address, order_items):
    errors = {}

    required = {
        "name": address.Name,
        "address": address.location,
        "city": address.City,
        "pincode": address.Pincode,
        "state": address.State,
        "phone": address.MobileNumber,
    }

    for key, value in required.items():
        if not value or not str(value).strip():
            errors[key] = "Missing"

    if not order_items.exists():
        errors["order_items"] = "No items"

    return errors


# =====================================================
# 🚚 CREATE SHIPROCKET ORDER (AUTO MODE)
# =====================================================

def create_shiprocket_order(order, address, order_items):
    """
    ✅ Prepaid only
    ✅ Auto courier assignment
    ✅ Auto AWB by Shiprocket
    ❌ No courier_company_id
    ❌ No assign_awb()
    """

    # 1️⃣ Validate
    errors = validate_address_for_shiprocket(address, order_items)
    if errors:
        return {"status": "error", "errors": errors}

    # 2️⃣ Serviceability
    service = check_shiprocket_service(address, order.total_price)
    if service.get("error"):
        return {"status": "error", "message": "Address not serviceable"}

    token = get_shiprocket_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 📦 SAFE FIXED PACKAGE (IMPORTANT)
    weight = 1.0
    length, breadth, height = 20, 15, 10

    # 3️⃣ Items
    items = []
    for item in order_items:
        unit_discount = (
            float(item.discount_amount or 0) / item.quantity
        ) if item.quantity else 0

        items.append({
            "name": item.product.name,
            "sku": item.product.sku or f"AUTO-{item.product.id}",
            "units": item.quantity,
            "selling_price": float(item.price),
            "discount": round(unit_discount, 2),
            "hsn": 441122
        })

    payload = {
        "order_id": f"ORD-{order.id}",
        "order_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),

        # ⚠️ EXACT NAME FROM SHIPROCKET PANEL
        "pickup_location": "warehouse",

        "comment": "Prepaid Order",
        "company_name": "PerFume Valley",

        # Billing
        "billing_customer_name": address.Name,
        "billing_address": address.location,
        "billing_city": address.City,
        "billing_pincode": address.Pincode,
        "billing_state": address.State,
        "billing_country": "India",
        "billing_email": address.email or "support@perfumevalley.in",
        "billing_phone": address.MobileNumber,

        # Shipping
        "shipping_is_billing": True,
        "shipping_customer_name": address.Name,
        "shipping_address": address.location,
        "shipping_city": address.City,
        "shipping_pincode": address.Pincode,
        "shipping_state": address.State,
        "shipping_country": "India",
        "shipping_phone": address.MobileNumber,

        "order_items": items,
        "payment_method": "Prepaid",

        "sub_total": float(order.total_price),

        # 📦 SAME PACKAGE AS SERVICEABILITY
        "weight": weight,
        "length": length,
        "breadth": breadth,
        "height": height
    }

    response = requests.post(
        "https://apiv2.shiprocket.in/v1/external/orders/create/adhoc",
        json=payload,
        headers=headers,
        timeout=15
    )

    data = response.json()

    if response.status_code != 200:
        return {"status": "error", "shiprocket": data}

    return {
        "status": "success",
        "shiprocket": data
    }

from django.core.mail import EmailMessage

def send_invoice_email(email, order):
    token = get_shiprocket_token()
    url = "https://apiv2.shiprocket.in/v1/external/orders/print/invoice"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "ids": [order.shiprocket_order_id]
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    if response.status_code == 200 and data.get("invoice_url"):
        invoice_url = data["invoice_url"]
        invoice_response = requests.get(invoice_url)

        if invoice_response.status_code == 200:
            mail = EmailMessage(
                subject="Your Order Invoice",
                body="Thank you for your order. Please find the invoice attached.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            mail.attach(
                f"invoice_{order.id}.pdf",
                invoice_response.content,
                "application/pdf"
            )
            mail.send()



def fetch_shiprocket_tracking(awb_code):
    url = f"https://apiv2.shiprocket.in/v1/external/courier/track/awb/{awb_code}"
    token = get_shiprocket_token()

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            tracking_data = response.json().get("tracking_data", {})

            shipment_tracks = tracking_data.get("shipment_track", [])
            if isinstance(shipment_tracks, dict):
                shipment_tracks = [shipment_tracks]
            elif not isinstance(shipment_tracks, list):
                shipment_tracks = []

            latest_track = shipment_tracks[-1] if shipment_tracks else {}

            return {
                'awb_code': latest_track.get('awb_code', ''),
                'courier_name': latest_track.get('courier_name', ''),
                'current_status': latest_track.get('current_status', ''),
                'origin': latest_track.get('origin', ''),
                'destination': latest_track.get('destination', ''),
                'etd': tracking_data.get('etd', ''),
                'track_url': tracking_data.get('track_url', ''),
                'shipment_tracks': shipment_tracks  # ✅ Full history, if you want to display in template
            }

        else:
            print("❌ Shiprocket tracking error:", response.status_code, response.text)

    except Exception as e:
        print("⚠️ Exception in fetch_shiprocket_tracking:", e)

    return {
        'awb_code': '',
        'courier_name': '',
        'current_status': '',
        'origin': '',
        'destination': '',
        'etd': '',
        'track_url': '',
        'shipment_tracks': []
    }






# Additional Shiprocket API integrations after order creation

import requests
from django.conf import settings

def assign_awb(shipment_id, payload=None):
    """
    Assigns AWB to a shipment.
    If the AWB is canceled, automatically retries with a new order (requires payload).
    """
    import datetime, requests, logging
    token = get_shiprocket_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    url = "https://apiv2.shiprocket.in/v1/external/courier/assign/awb"

    try:
        # Step 1: Assign AWB
        response = requests.post(url, json={"shipment_id": shipment_id}, headers=headers, timeout=30)

        # ✅ Debug log both status + body
        print(f"📦 AWB Request URL: {url}")
        print(f"📤 AWB Request Payload: {{'shipment_id': {shipment_id}}}")
        print(f"📥 AWB Response Status: {response.status_code}")
        print(f"📥 AWB Response Text: {response.text}")

        awb_result = response.json()

    except Exception as e:
        print(f"❌ Exception during AWB assignment for shipment {shipment_id}: {e}")
        return None

    # Step 2: Check if AWB is canceled
    awb_code = awb_result.get("response", {}).get("data", {}).get("awb_code", "")
    if awb_code:
        tracking_info = fetch_shiprocket_tracking(awb_code)
        if tracking_info.get("current_status", "").lower() == "canceled":
            print(f"⚠️ AWB {awb_code} is canceled.")

            # Retry only if payload is provided
            if payload:
                print("🔄 Retrying with a new order_id...")
                payload["order_id"] = f"{payload['order_id']}-{int(datetime.datetime.now().timestamp())}"
                retry_url = "https://apiv2.shiprocket.in/v1/external/orders/create/adhoc"
                retry_resp = requests.post(retry_url, json=payload, headers=headers)
                print(f"🔄 Retry Status: {retry_resp.status_code}")
                print(f"🔄 Retry Shiprocket Response: {retry_resp.text}")

                retry_data = retry_resp.json()
                if retry_resp.status_code == 200 and "shipment_id" in retry_data:
                    new_shipment_id = retry_data.get("shipment_id")
                    return assign_awb(new_shipment_id, payload=None)  # Recursion without retry loop
                else:
                    print("❌ Retry failed. No new shipment created.")
            else:
                print("⚠️ No payload provided. Cannot retry AWB assignment.")
    return awb_result


def generate_pickup(shipment_id):
    url = "https://apiv2.shiprocket.in/v1/external/courier/generate/pickup"
    token = get_shiprocket_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "shipment_id": shipment_id
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

def generate_manifest(shipment_id):
    url = "https://apiv2.shiprocket.in/v1/external/manifests/generate"
    token = get_shiprocket_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "shipment_id": shipment_id
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

def print_manifest(shipment_id):
    url = "https://apiv2.shiprocket.in/v1/external/manifests/print"
    token = get_shiprocket_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "shipment_id": shipment_id
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()  # PDF URL will be in this

def generate_label(shipment_id):
    url = "https://apiv2.shiprocket.in/v1/external/courier/generate/label"
    token = get_shiprocket_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "shipment_id": shipment_id
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()  # PDF URL

# def print_invoice(order_id):
#     url = "https://apiv2.shiprocket.in/v1/external/orders/print/invoice"
#     token = get_shiprocket_token()
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {token}"
#     }
#     payload = {
#         "ids": [order_id]
#     }
#     response = requests.post(url, json=payload, headers=headers)
#     return response.json()  # PDF URL

def track_order_by_awb(awb_code):
    url = f"https://apiv2.shiprocket.in/v1/external/courier/track/awb/{awb_code}"
    token = get_shiprocket_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    return response.json()

# subscriptions/utils.py

from pywebpush import webpush


def send_push_notification(guest_id, title, message):
    try:
        subscription = PushSubscription.objects.get(guest_id=guest_id)

        payload = json.dumps({
            "title": title,
            "body": message
        })

        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": subscription.keys
            },
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_ADMIN_EMAIL}
        )

    except PushSubscription.DoesNotExist:
        pass
    except Exception as e:
        print("Push notification failed:", e)


def run_shiprocket_now(order_id):
    from admin_panel.models import Order

    order = Order.objects.get(id=order_id)

    print("🚀 Creating Shiprocket order...")
    resp = create_shiprocket_order(
        order,
        order.address,
        order.items.all()
    )

    if resp.get("status") != "success":
        print("❌ Failed:", resp)
        return resp

    print("📦 Assigning AWB...")
    awb_resp = assign_awb(order.shiprocket_shipment_id)

    print("✅ Done")
    return {
        "order_id": order.id,
        "shiprocket_order_id": order.shiprocket_order_id,
        "shipment_id": order.shiprocket_shipment_id,
        "awb": order.shiprocket_awb_code,
    }
