import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PerfumeValley.settings")

app = Celery("PerfumeValley")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ✅ Celery Beat Schedule
app.conf.beat_schedule = {

    # 1️⃣ Create Shiprocket Orders
    "create-shiprocket-orders-every-1-min": {
        "task": "admin_panel.tasks.schedule_pending_shiprocket_orders",
        "schedule": 60.0,
    },

    # 2️⃣ FETCH AWB (MOST IMPORTANT FOR UI)
    "fetch-shiprocket-awb-every-2-min": {
        "task": "admin_panel.tasks.schedule_awb_fetch",
        "schedule": 120.0,
    },

    # 3️⃣ Send Invoices
    "send-invoices-every-5-min": {
        "task": "admin_panel.tasks.send_invoice_email_task",
        "schedule": 300.0,
    },

    # 4️⃣ Low Stock Alerts
    "check-low-stock-every-1-min": {
        "task": "admin_panel.tasks.notify_low_stock_task",
        "schedule": 60.0,
    },

    # 5️⃣ Fetch Shiprocket Tracking Status
    "fetch-shiprocket-tracking-every-5-min": {
        "task": "admin_panel.tasks.fetch_tracking_status",
        "schedule": 300.0,
    },
}
