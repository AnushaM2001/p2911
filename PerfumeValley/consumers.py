# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
# from django.contrib.auth.models import User
from user_panel.models import Cart

# class CartConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         self.user_id = self.scope['url_route']['kwargs']['user_id']
#         self.cart_group_name = f'user_{self.user_id}_cart'

#         # Join cart group
#         await self.channel_layer.group_add(
#             self.cart_group_name,
#             self.channel_name
#         )
#         await self.accept()

#     async def disconnect(self, close_code):
#         # Leave cart group
#         await self.channel_layer.group_discard(
#             self.cart_group_name,
#             self.channel_name
#         )

#     async def cart_update(self, event):
#         # Send message to WebSocket
#         await self.send(text_data=json.dumps({
#             'action': event['action'],
#             'item_id': event.get('item_id'),
#             'item_key': event.get('item_key'),
#             'quantity': event.get('quantity'),
#             'cart_count': event['cart_count'],
#             'is_empty': event['is_empty']
#         }))

#     @database_sync_to_async
#     def get_cart_count(self, user_id):
#         return Cart.objects.filter(user_id=user_id).count()



class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        # ✅ ONLY admins
        if user and user.is_authenticated and user.is_staff:
            self.group_name = "admin_notifications"
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            "admin_notifications",
            self.channel_name
        )

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({
            "message": event.get("message"),
            "counts": event.get("counts", {}),
            "category": event.get("category"),
        }))


# class WishlistConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         user = self.scope['user']
#         if not user.is_authenticated:
#             await self.close()
#             return

#         self.group_name = f"wishlist_{user.id}"
#         await self.channel_layer.group_add(self.group_name, self.channel_name)
#         await self.accept()

#     async def disconnect(self, close_code):
#         if hasattr(self, "group_name"):
#             await self.channel_layer.group_discard(self.group_name, self.channel_name)

#     async def wishlist_update(self, event):
#         await self.send(text_data=json.dumps({
#             "count": event["count"]
#         }))


from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from django.utils.timezone import now
from user_panel.models import HelpQuery, HelpQueryMessage



class HelpQueryConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.query_id = self.scope["url_route"]["kwargs"]["query_id"]
        self.room_group_name = f"help_query_{self.query_id}"

        # 🧠 Identify user
        self.user = self.scope.get("user")
        self.guest_id = self.scope["session"].get("guest_id")

        # 🔒 Permission check
        if not await self.can_access_query():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message", "").strip()
        if not message:
            return

        sender = "Admin" if self.is_admin() else "User"

        await self.save_message(sender, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": sender,
                "time": now().strftime("%H:%M"),
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    # =========================
    # 🔒 PERMISSION
    # =========================
    def is_admin(self):
        return self.user and self.user.is_authenticated and self.user.is_staff

    @database_sync_to_async
    def can_access_query(self):
        if self.is_admin():
            return True

        return HelpQuery.objects.filter(
            id=self.query_id,
            guest_id=self.guest_id
        ).exists()

    # =========================
    # 💾 SAVE MESSAGE
    # =========================
    @database_sync_to_async
    def save_message(self, sender, message):
        query = HelpQuery.objects.get(id=self.query_id)

        HelpQueryMessage.objects.create(
            query=query,
            sender=sender,
            text=message
        )

        # Update status
        query.status = "Solved" if sender == "Admin" else "In Progress"
        query.save(update_fields=["status"])
