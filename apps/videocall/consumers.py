import json
from channels.generic.websocket import AsyncWebsocketConsumer

# Dictionary to track active connections per room: { room_name: set(user_ids) }
ACTIVE_CALL_USERS = {}

class VideoCallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        # 1. Reject unauthenticated WebSocket connections immediately
        if not self.user.is_authenticated:
            await self.close()
            return

        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'call_{self.room_name}'
        
        # Initialize room tracking if it doesn't exist
        if self.room_name not in ACTIVE_CALL_USERS:
            ACTIVE_CALL_USERS[self.room_name] = set()

        # 2. Check if this user is already connected in another tab/device
        if self.user.id in ACTIVE_CALL_USERS[self.room_name]:
            # Close the connection if a session already exists for this user
            await self.close(code=4001) # Custom close code for duplicate tab/device
            return

        # Register user as active in this room
        ACTIVE_CALL_USERS[self.room_name].add(self.user.id)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Remove user from active tracking when they leave or close the tab
        if hasattr(self, 'room_name') and self.room_name in ACTIVE_CALL_USERS:
            if hasattr(self, 'user') and self.user.id in ACTIVE_CALL_USERS[self.room_name]:
                ACTIVE_CALL_USERS[self.room_name].remove(self.user.id)
                if not ACTIVE_CALL_USERS[self.room_name]:
                    del ACTIVE_CALL_USERS[self.room_name]

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'forward_signal',
                'message': data,
                'sender': self.channel_name
            }
        )

    async def forward_signal(self, event):
        # Broadcast to the other person in the room, not the sender
        if self.channel_name != event['sender']:
            await self.send(text_data=json.dumps(event['message']))