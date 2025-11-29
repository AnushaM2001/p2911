# asgi.py or routing.py
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/cart/(?P<user_id>\w+)/$', consumers.CartConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/wishlist/$', consumers.WishlistConsumer.as_asgi()),


]