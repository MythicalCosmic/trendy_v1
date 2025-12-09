import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from users.models import SupportTicket, TicketMessage, User


class TicketChatConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.user = self.scope['user'] or "AnonymousUser"  # safe fallback

        print("\n" + "="*50)
        print(f"WEBSOCKET CONNECT: ticket/{self.ticket_id}")
        print(f"User: {self.user} (authenticated: {self.user.is_authenticated if hasattr(self.user, 'is_authenticated') else 'NO'})")
        print("="*50 + "\n")

        # FORCE ACCEPT EVERYTHING — FOR TESTING ONLY
        self.room_group_name = f'ticket_{self.ticket_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()   # This is the only line that matters right now

        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'YOU ARE CONNECTED! Development mode bypass active',
            'ticket_id': self.ticket_id,
            'user': str(self.user)
        }))
    
    async def disconnect(self, close_code):
        await self.mark_user_offline()
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'read_receipt':
                await self.handle_read_receipt(data)
            elif message_type == 'file_upload':
                await self.handle_file_upload(data)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
    
    async def handle_chat_message(self, data):
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return
        
        message_obj = await self.save_message(message_text)
        
        if not message_obj:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to send message'
            }))
            return
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message_obj['id'],
                'message': message_obj['message'],
                'user': message_obj['user'],
                'message_type': message_obj['message_type'],
                'attachments': message_obj['attachments'],
                'created_at': message_obj['created_at'],
                'sender_id': self.user.id
            }
        )
    
    async def handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'user_name': f"{self.user.first_name} {self.user.last_name}",
                'is_typing': is_typing
            }
        )
    
    async def handle_read_receipt(self, data):
        message_id = data.get('message_id')
        
        if message_id:
            await self.mark_message_read(message_id)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'message_id': message_id,
                    'read_by': self.user.id
                }
            )
    
    async def handle_file_upload(self, data):
        file_data = data.get('file')
        
        if file_data:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'file_uploaded',
                    'file': file_data,
                    'uploaded_by': self.user.id
                }
            )
    
    
    async def chat_message(self, event):
        if event.get('sender_id') != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'chat_message',
                'message_id': event['message_id'],
                'message': event['message'],
                'user': event['user'],
                'message_type': event['message_type'],
                'attachments': event.get('attachments', []),
                'created_at': event['created_at']
            }))
    
    async def typing_indicator(self, event):
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
    
    async def read_receipt(self, event):
        if event['read_by'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'read_receipt',
                'message_id': event['message_id'],
                'read_by': event['read_by']
            }))
    
    async def file_uploaded(self, event):
        if event['uploaded_by'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'file_uploaded',
                'file': event['file']
            }))
    
    async def ticket_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ticket_update',
            'event_type': event['event_type'],
            'data': event['data']
        }))
    
    
    @database_sync_to_async
    def verify_ticket_access(self):
        try:
            ticket = SupportTicket.objects.get(id=self.ticket_id)
        
            if ticket.user_id == self.user or ticket.assigned_to == self.user:
                return True

            if self.user.role == 'ADMIN':
                return True
            
            return False
        except SupportTicket.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, message_text):
        try:
            ticket = SupportTicket.objects.get(id=self.ticket_id)

            if self.user == ticket.user_id:
                message_type = 'USER'
            elif self.user.role == 'ADMIN':
                message_type = 'ADMIN'
            else:
                message_type = 'SYSTEM'
            
            message = TicketMessage.objects.create(
                ticket_id=ticket,
                user_id=self.user,
                message_type=message_type,
                message=message_text
            )
            
            ticket.updated_at = timezone.now()
            ticket.save(update_fields=['updated_at'])
            
            return {
                'id': message.id,
                'message': message.message,
                'user': {
                    'id': self.user.id,
                    'name': f"{self.user.first_name} {self.user.last_name}",
                    'role': self.user.role
                },
                'message_type': message.message_type,
                'attachments': message.attachments,
                'created_at': message.created_at.isoformat()
            }
        except Exception:
            return None
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        pass
    
    @database_sync_to_async
    def mark_user_online(self):
        """Mark user as online for this ticket"""
        # Can use Redis or cache to track online users
        pass
    
    @database_sync_to_async
    def mark_user_offline(self):
        """Mark user as offline for this ticket"""
        pass


class TicketQueueConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(
            'ticket_queue',
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            'ticket_queue',
            self.channel_name
        )
    
    async def queue_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'queue_update',
            'queue_length': event['queue_length']
        }))


class AdminDashboardConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated or self.user.role != 'ADMIN':
            await self.close()
            return
        

        await self.channel_layer.group_add(
            'admins_online',
            self.channel_name
        )
        
        await self.channel_layer.group_add(
            f'admin_{self.user.id}',
            self.channel_name
        )
        
        await self.accept()

        stats = await self.get_dashboard_stats()
        await self.send(text_data=json.dumps({
            'type': 'initial_stats',
            'stats': stats
        }))
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            'admins_online',
            self.channel_name
        )
        
        await self.channel_layer.group_discard(
            f'admin_{self.user.id}',
            self.channel_name
        )
    
    async def ticket_update(self, event):
        await self.send(text_data=json.dumps({
            'type': event['event_type'],
            'data': event['data']
        }))
    
    @database_sync_to_async
    def get_dashboard_stats(self):
        from django.db.models import Count, Q
        
        stats = SupportTicket.objects.aggregate(
            total=Count('id'),
            open=Count('id', filter=Q(status='OPEN')),
            in_progress=Count('id', filter=Q(status='IN_PROGRESS')),
            waiting=Count('id', filter=Q(status='WAITING')),
            my_tickets=Count('id', filter=Q(assigned_to=self.user))
        )
        
        return stats


# routing.py configuration
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/ticket/(?P<ticket_id>\w+)/$', consumers.TicketChatConsumer.as_asgi()),
    re_path(r'ws/queue/$', consumers.TicketQueueConsumer.as_asgi()),
    re_path(r'ws/admin/dashboard/$', consumers.AdminDashboardConsumer.as_asgi()),
]
"""