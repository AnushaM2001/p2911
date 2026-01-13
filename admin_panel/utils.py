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

#service check
def check_shiprocket_service(address, declared_value=1000):
    if not address:
        return {"error": "Address not provided"}

    token = get_shiprocket_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    params = {
        "pickup_postcode": "500008",
        "delivery_postcode": address.Pincode,
        "cod": 0,
        "weight": 0.5,
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
        return {"error": "No couriers available", "raw": data}

    best = min(
        couriers,
        key=lambda x: x.get("freight_charge") or float("inf")
    )

    return {
        "best_courier": {
            "name": best.get("courier_name"),
            "freight_charge": best.get("freight_charge"),
            "courier_company_id": best.get("courier_company_id"),
            "etd": best.get("etd"),
        }
    }


def validate_address_for_shiprocket(address, order, order_items):
    errors = {}

    required_fields = {
        "billing_customer_name": address.Name,
        "billing_address": address.location,
        "billing_city": address.City,
        "billing_pincode": address.Pincode,
        "billing_state": address.State,
        "billing_country": "India",
        "billing_phone": address.MobileNumber,
    }

    for key, value in required_fields.items():
        if not value or not str(value).strip():
            errors[key] = "Missing or empty"

    if not order_items:
        errors["order_items"] = "No items provided"

    return errors




import requests
import datetime
import json
from admin_panel.views import notify_admins


import datetime
import json

import datetime
import requests
import json

def create_shiprocket_order(order, address, order_items):
    """
    Create Shiprocket order without product weight.
    Handles primary + fallback courier, AWB assignment, and logging.
    """
    # 1️⃣ Validate address
    validation_errors = validate_address_for_shiprocket(address, order, order_items)
    if validation_errors:
        return {"status": "error", "message": "Validation failed", "errors": validation_errors}

    # 2️⃣ Shiprocket token
    token = get_shiprocket_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 3️⃣ Totals
    giftwrap_charge = 150 if any(getattr(item, 'gift_wrap', False) for item in order_items) else 0
    platform_fee = sum(float(getattr(item, "platform_fee", 0) or 0) for item in order_items)
    delivery_charge = sum(float(getattr(item, "delivery_charges", 0) or 0) for item in order_items)
    total_discount = sum(float(item.discount_amount or 0) for item in order_items)
    order_total = float(order.total_price)

    # 4️⃣ Default weight
    DEFAULT_ITEM_WEIGHT = 0.5  # kg per item
    total_weight = sum(DEFAULT_ITEM_WEIGHT * item.quantity for item in order_items)

    # Standard box dimensions (cm)
    length, breadth, height = 10, 15, 20
    volumetric_weight = (length * breadth * height) / 5000
    shipping_weight = max(total_weight, volumetric_weight)

    # 5️⃣ Select primary and fallback courier
    primary_courier, fallback_courier = select_couriers_by_etd(address, order_total, shipping_weight)
    if not primary_courier:
        return {"status": "error", "message": "No couriers available for this address"}

    # 6️⃣ Prepare order items
    item_list = []
    for item in order_items:
        sku_value = item.product.sku.strip() if item.product.sku else f"AUTO-{item.product.id}"
        unit_discount = round(float(item.discount_amount or 0) / item.quantity, 2) if item.quantity else 0
        item_list.append({
            "name": item.product.name,
            "category": item.product.category.name if item.product.category else "General",
            "sku": sku_value,
            "units": item.quantity,
            "selling_price": float(item.price),
            "discount": unit_discount,
            "hsn": 441122
        })

    # 7️⃣ Build payload
    payload = {
        "order_id": f"ORD-{order.id}",
        "order_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "pickup_location": "warehouse",
        "comment": "Placed via Razorpay",
        "reseller_name": "Mohammed",
        "company_name": "PerFume Valley",
        "billing_customer_name": address.Name,
        "billing_last_name": "",
        "billing_address": address.location,
        "billing_address_2": address.Landmark or "",
        "billing_isd_code": "+91",
        "billing_city": address.City,
        "billing_pincode": address.Pincode,
        "billing_state": address.State,
        "billing_country": "India",
        "billing_email": address.email or "support@perfumevalley.in",
        "billing_phone": address.MobileNumber,
        "billing_alternate_phone": address.Alternate_MobileNumber,
        "shipping_is_billing": True,
        "shipping_customer_name": address.Name,
        "shipping_last_name": "",
        "shipping_address": address.location,
        "shipping_address_2": address.Landmark or "",
        "shipping_city": address.City,
        "shipping_pincode": address.Pincode,
        "shipping_state": address.State,
        "shipping_country": "India",
        "shipping_email": address.email or "support@perfumevalley.in",
        "shipping_phone": address.MobileNumber,
        "order_items": item_list,
        "payment_method": "Prepaid",
        "shipping_charges": 0,
        "giftwrap_charges": round(giftwrap_charge, 2),
        "transaction_charges": round(platform_fee + delivery_charge, 2),
        "total_discount": round(total_discount, 2),
        "sub_total": round(order_total, 2),
        "courier_company_id": primary_courier["courier_company_id"],
        "length": length,
        "breadth": breadth,
        "height": height,
        "weight": shipping_weight,
        "ewaybill_no": "",
        "customer_gstin": "",
        "invoice_number": "",
        "order_type": ""
    }

    print("✅ Shiprocket Payload:", json.dumps(payload, indent=4))

    # 8️⃣ Create order
    response = requests.post(
        "https://apiv2.shiprocket.in/v1/external/orders/create/adhoc",
        json=payload,
        headers=headers,
        timeout=15
    )
    response_data = response.json()
    shiprocket_shipment_id = response_data.get("shipment_id")
    print("📦 Shiprocket Order Response:", response_data)

    awb_code, courier_name = None, None

    # 9️⃣ Assign AWB
    if shiprocket_shipment_id:
        awb_response = assign_awb(shiprocket_shipment_id, payload=payload)
        awb_data = awb_response.get("response", {}).get("data", {})
        awb_code = awb_data.get("awb_code") or response_data.get("awb_code")
        courier_name = awb_data.get("courier_name") or response_data.get("courier_name")
        print("🚚 AWB Assignment Response:", awb_response)

    # 10️⃣ Retry with fallback if primary fails
    if not awb_code and fallback_courier:
        print(f"⚠️ Primary courier failed, retrying with fallback: {fallback_courier['courier_name']}")
        payload["courier_company_id"] = fallback_courier["courier_company_id"]
        fallback_resp = requests.post(
            "https://apiv2.shiprocket.in/v1/external/orders/create/adhoc",
            json=payload,
            headers=headers,
            timeout=15
        )
        fallback_data = fallback_resp.json()
        fallback_shipment_id = fallback_data.get("shipment_id")
        print("📦 Fallback Order Response:", fallback_data)

        if fallback_shipment_id:
            awb_response = assign_awb(fallback_shipment_id, payload=payload)
            awb_data = awb_response.get("response", {}).get("data", {})
            awb_code = awb_data.get("awb_code") or fallback_data.get("awb_code")
            courier_name = awb_data.get("courier_name") or fallback_data.get("courier_name")
            shiprocket_shipment_id = fallback_shipment_id

    # 11️⃣ Update Order in DB
    if awb_code:
        order.shiprocket_awb_code = awb_code
        order.shiprocket_courier_name = courier_name
        order.status = "awb_assigned"
        order.shiprocket_order_id = response_data.get("order_id")
        order.shiprocket_shipment_id = shiprocket_shipment_id
        order.save(update_fields=[
            "shiprocket_awb_code", "shiprocket_courier_name",
            "status", "shiprocket_order_id", "shiprocket_shipment_id"
        ])
        print(f"✅ Order {order.id} AWB assigned: {awb_code} Courier: {courier_name}")
    else:
        print(f"⚠️ AWB not assigned for Order {order.id}")

    # 12️⃣ Return result
    tracking_url = f"https://apiv2.shiprocket.in/v1/external/courier/track?shipment_id={shiprocket_shipment_id}"
    label_url = f"https://apiv2.shiprocket.in/v1/external/courier/generate/label?shipment_id={shiprocket_shipment_id}"

    return {
        "status": "success" if awb_code else "error",
        "shiprocket_response": response_data,
        "tracking_url": tracking_url,
        "label_url": label_url,
        "sent_payload": payload,
        "awb_response": awb_response if shiprocket_shipment_id else None
    }


def select_couriers_by_etd(address, declared_value, weight):
    """
    Returns primary and fallback courier based on ETD (fastest delivery first).
    """
    courier_info = check_shiprocket_service(address, declared_value=declared_value)
    couriers = courier_info.get("data", {}).get("available_courier_companies", [])

    if not couriers:
        return None, None

    # Sort by ETD (fastest delivery), then freight charge
    sorted_couriers = sorted(couriers, key=lambda x: (x.get("etd", 99), x.get("freight_charge", 9999)))
    primary = sorted_couriers[0] if len(sorted_couriers) > 0 else None
    fallback = sorted_couriers[1] if len(sorted_couriers) > 1 else None
    return primary, fallback


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
