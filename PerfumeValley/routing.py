# asgi.py or routing.py
from django.urls import path, re_path

from . import consumers

websocket_urlpatterns = [
    # re_path(r'ws/cart/(?P<user_id>\w+)/$', consumers.CartConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    # re_path(r'ws/wishlist/$', consumers.WishlistConsumer.as_asgi()),
    re_path(r'ws/help-query/(?P<query_id>\d+)/$', consumers.HelpQueryConsumer.as_asgi()),
]

