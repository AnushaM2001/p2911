from django.conf import settings
from django.core.mail import send_mail
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from admin_panel.models import Notification, AdminUser


def notify_admins(message, category="orders"):
    admin_user = AdminUser.objects.first()
    if not admin_user:
        print("No admin user found!")
        return

    # ✅ Prevent duplicate unread notifications
    if Notification.objects.filter(
        user=admin_user,
        message=message,
        category=category,
        is_read=False
    ).exists():
        print(f"Duplicate notification skipped: {message}")
        return

    # Save notification
    Notification.objects.create(
        user=admin_user,
        message=message,
        category=category
    )

    # Fresh unread counts
    counts = {
        "orders": Notification.objects.filter(
            user=admin_user, category="orders", is_read=False
        ).count(),
        "stocks": Notification.objects.filter(
            user=admin_user, category="stocks", is_read=False
        ).count(),
        "queries": Notification.objects.filter(
            user=admin_user, category="queries", is_read=False
        ).count(),
    }

    # WebSocket push
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "admin_notifications",
        {
            "type": "send_notification",
            "message": message,
            "counts": counts,
            "category": category,
        }
    )

    # Email notification
    if admin_user.email:
        try:
            send_mail(
                subject=f"New Admin Notification - {category.capitalize()}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error sending email: {e}")
