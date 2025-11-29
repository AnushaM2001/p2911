import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PerfumeValley.settings")

app = Celery("PerfumeValley")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ✅ Celery Beat Schedule (runs every 1 min)
app.conf.beat_schedule = {
    "create-shiprocket-orders-every-1-min": {
        "task": "admin_panel.tasks.process_order_with_shiprocket",
        "schedule": 60.0,  # every 5 minute
    },
    "send-invoices-every-5-min": {
        "task": "admin_panel.tasks.send_invoice_email_task",
        "schedule": 300.0,  # every 5 minute
    },
    "check-low-stock-every-1-min": {
        "task": "admin_panel.tasks.notify_low_stock_task",
        "schedule": 60.0,  # every 5 minute
    },
    'fetch-shiprocket-tracking-every-5-min': {
        'task': 'admin_panel.tasks.fetch_tracking_status',
        'schedule': 300.0,  # every 5 minutes
    },
}