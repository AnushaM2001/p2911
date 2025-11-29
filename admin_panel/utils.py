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
def check_shiprocket_service(user, address_id, declared_value=1000):
    try:
        address = AddressModel.objects.get(id=address_id, user=user)
    except AddressModel.DoesNotExist:
        return {"error": "Address not found"}

    token = get_shiprocket_token()

    headers = {
        'Authorization': f'Bearer {token}'
    }

    params = {
        'pickup_postcode': '500008',  # replace with your warehouse pincode
        'delivery_postcode': address.Pincode,
        'cod': 0,  # prepaid
        'weight': 0.5,
        'order_type': 1,
        'declared_value': declared_value
    }

    response = requests.get(
        'https://apiv2.shiprocket.in/v1/external/courier/serviceability/',
        headers=headers,
        params=params
    )

    data = response.json()
    couriers = data.get('data', {}).get('available_courier_companies', [])

    if not couriers:
        return {"error": "No couriers available", "raw": data}

    # Automatically pick the best courier (lowest freight_charge or fastest delivery)
    best = sorted(couriers, key=lambda x: (x.get('freight_charge') or 9999))[0]

    return {
        "best_courier": {
            "name": best['courier_name'],
            "freight_charge": best['freight_charge'],
            "courier_company_id": best['courier_company_id'],
            "etd": best['etd'],
            # "estimated_delivery_days": best['estimated_delivery_days'],
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
        "billing_email": order.user.email,
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

def create_shiprocket_order(order, address, order_items):
    import datetime
    import json

    # Step 1: Validate Address (unchanged)
    validation_errors = validate_address_for_shiprocket(address, order, order_items)
    if validation_errors:
        return {
            "status": "error",
            "message": "Validation failed before API call",
            "errors": validation_errors
        }

    # Step 2: Shiprocket Token (unchanged)
    token = get_shiprocket_token()

    #step 2 
    courier_info = check_shiprocket_service(order.user, address.id)
    if not courier_info or "best_courier" not in courier_info:
        return {"status": "error", "message": "No eligible courier found", "details": courier_info}

    best_courier_id = courier_info['best_courier']['courier_company_id']

    # Step 3: Totals
    giftwrap_charge = 150 if any(getattr(item, 'gift_wrap', False) for item in order_items) else 0
    platform_fee = sum(
    float(getattr(item, "platform_fee", 0) or 0) for item in order_items
)

    delivery_charge = sum(
    float(getattr(item, "delivery_charges", 0) or 0) for item in order_items
)

    sub_total = sum(float(item.price) * item.quantity for item in order_items)
    total_discount = sum(float(item.discount_amount or 0) for item in order_items)
    # Use order.total_price from the Order table for order_total
    order_total = float(order.total_price)

    # Step 4: Build item list - FIX DISCOUNT HERE
    item_list = []
    for item in order_items:
        sku_value = item.product.sku.strip() if item.product.sku else f"AUTO-{item.product.id}"
        item_price = float(item.price)
        item_qty = item.quantity
        item_discount = float(item.discount_amount or 0)

        # Per-unit discount MUST BE POSITIVE (Shiprocket subtracts this from the price)
        unit_discount = round(item_discount / item_qty, 2) if item_qty else 0

        item_list.append({
            "name": item.product.name,
            "category": item.product.category.name if item.product.category else "General",
            "sku": sku_value,
            "units": item_qty,
            "selling_price": item_price,
            "discount": unit_discount,  # Per-unit discount
            "hsn": 441122
        })

    # Step 5: Build payload
    payload = {
        "order_id": f"ORD-{order.id}",
        # "courier_id" : order.shiprocket_courier_id,
        "courier_company_id": best_courier_id,
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
        "billing_email": order.user.email,
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
        "shipping_email": order.user.email,
        "shipping_phone": address.MobileNumber,

        "order_items": item_list,
        "payment_method": "Prepaid",
        "shipping_charges": 0,
        "giftwrap_charges": round(giftwrap_charge, 2),
        "transaction_charges": round(platform_fee + delivery_charge, 2),
        "total_discount": round(total_discount, 2),  # Set total discount as positive value
        "sub_total": round(order_total, 2),
        # "order_total": round(order_total, 2),

        "length": 10,
        "breadth": 15,
        "height": 20,
        "weight": 2.0,
        "ewaybill_no": "",
        "customer_gstin": "",
        "invoice_number": "",
        "order_type": "",
        # "courier_id": best_courier_id,

    }

    print("✅ Final Payload Sent to Shiprocket:")
    print(json.dumps(payload, indent=4))

    headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    # Step 5: Send request to Shiprocket
    response = requests.post(
        "https://apiv2.shiprocket.in/v1/external/orders/create/adhoc",
        json=payload,
        headers=headers
    )
    print("Shiprocket response full text:", response.text)
    response_data = response.json()

    if response.status_code == 200 and "order_id" in response_data:
        shiprocket_order_id = response_data.get("order_id")
        shiprocket_shipment_id = response_data.get("shipment_id")
        # Save to order
        order.shiprocket_courier_id = best_courier_id
        order.shiprocket_order_id = shiprocket_order_id
        order.shiprocket_shipment_id = shiprocket_shipment_id

        # 🚀 Try assigning AWB
        awb_response = assign_awb(shiprocket_shipment_id,payload=payload)
        print("AWB Assignment Response:", awb_response)

        awb_data = awb_response.get("response", {}).get("data", {})

        # ✅ Fallback if AWB already assigned
        awb_code = awb_data.get("awb_code") or response_data.get("awb_code", "")
        courier_name = awb_data.get("courier_name") or response_data.get("courier_name", "")

        if awb_code:
            order.shiprocket_awb_code = awb_code
            order.shiprocket_courier_name = courier_name
            order.status = "awb_assigned"
            order.save(update_fields=[
                'shiprocket_order_id',
                'shiprocket_shipment_id',
                'shiprocket_awb_code',
                'shiprocket_courier_name',
                'shiprocket_courier_id',  # Save courier ID too
                'status'
            ])
            notify_admins(f"✅ Order is Placed {order.id}-{order.shiprocket_order_id} - {order.user.email}", category="orders")

            print(f"✅ Order updated with AWB: {awb_code}, Courier: {courier_name}")
        else:
            # Just save order ID and shipment ID if AWB failed
            order.save(update_fields=['shiprocket_order_id', 'shiprocket_shipment_id'])
            print("⚠️ AWB code not assigned")

        # Generate URLs
        tracking_url = f"https://apiv2.shiprocket.in/v1/external/courier/track?shipment_id={shiprocket_shipment_id}"
        label_url = f"https://apiv2.shiprocket.in/v1/external/courier/generate/label?shipment_id={shiprocket_shipment_id}"

        return {
            "status": "success",
            "status_code": 200,
            "shiprocket_response": response_data,
            "tracking_url": tracking_url,
            "label_url": label_url,
            "sent_payload": payload,
            "awb_response": awb_response
        }

    # Failure
    return {
        "status": "error",
        "status_code": response.status_code,
        "shiprocket_response": response_data,
        "sent_payload": payload
    }

from django.core.mail import EmailMessage

def send_invoice_email(user, order):
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

        # Download the invoice PDF
        invoice_response = requests.get(invoice_url)
        if invoice_response.status_code == 200:
            email = EmailMessage(
                subject='Your Order Invoice',
                body='Thank you for your order. Please find your invoice attached.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach(f'invoice_{order.id}.pdf', invoice_response.content, 'application/pdf')
            email.send()



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


def send_push_notification(user, title, message):
    try:
        subscription = PushSubscription.objects.get(user=user)
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
    except Exception as e:
        print(f"[!] Push failed for {user.email}: {e}")
