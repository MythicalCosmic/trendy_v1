# services/ticket_service.py
import secrets
import redis
import json
from datetime import timedelta
from django.db import transaction, models
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.cache import cache
from django.core.files.storage import default_storage
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from users.models import (
    SupportTicket, TicketMessage, TicketAssignment,
    TicketStatusHistory, AdminAvailability, User
)


class TicketQueueManager:
    """Redis-based queue manager for high-performance operations"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        self.queue_key = 'ticket_queue'
        self.active_tickets_key = 'active_tickets'
    
    def add_to_queue(self, ticket_id, priority='MEDIUM'):
        """Add ticket to Redis queue with priority scoring"""
        priority_scores = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'URGENT': 4}
        score = priority_scores.get(priority, 2) * 1000 + timezone.now().timestamp()
        
        self.redis_client.zadd(self.queue_key, {str(ticket_id): score})
        return self.get_position(ticket_id)
    
    def remove_from_queue(self, ticket_id):
        """Remove ticket from queue when assigned"""
        self.redis_client.zrem(self.queue_key, str(ticket_id))
    
    def get_position(self, ticket_id):
        """Get ticket position in queue (0-indexed)"""
        rank = self.redis_client.zrank(self.queue_key, str(ticket_id))
        return rank + 1 if rank is not None else 0
    
    def get_next_ticket(self):
        """Get highest priority ticket from queue"""
        result = self.redis_client.zrange(self.queue_key, -1, -1)
        return int(result[0]) if result else None
    
    def get_queue_length(self):
        """Get total tickets in queue"""
        return self.redis_client.zcard(self.queue_key)
    
    def mark_ticket_active(self, ticket_id, admin_id):
        """Mark ticket as actively being handled"""
        data = {
            'admin_id': admin_id,
            'started_at': timezone.now().isoformat()
        }
        self.redis_client.hset(self.active_tickets_key, str(ticket_id), json.dumps(data))
    
    def unmark_ticket_active(self, ticket_id):
        """Remove ticket from active handling"""
        self.redis_client.hdel(self.active_tickets_key, str(ticket_id))


class FileUploadManager:
    """Handle file uploads for ticket messages"""
    
    @staticmethod
    def save_attachment(file, ticket_id):
        """Save file and return URL"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"tickets/{ticket_id}/{timestamp}_{file.name}"
        
        path = default_storage.save(filename, file)
        url = default_storage.url(path)
        
        return {
            'filename': file.name,
            'url': url,
            'size': file.size,
            'content_type': file.content_type
        }
    
    @staticmethod
    def validate_file(file, max_size_mb=10):
        """Validate file upload"""
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'text/plain'
        ]
        
        if file.size > max_size_mb * 1024 * 1024:
            return False, f'File too large. Max size: {max_size_mb}MB'
        
        if file.content_type not in allowed_types:
            return False, 'File type not allowed'
        
        return True, None


class TicketNotificationService:
    """WebSocket notification service for real-time updates"""
    
    @staticmethod
    def notify_user(user_id, event_type, data):
        """Send real-time notification to user"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}',
            {
                'type': 'ticket_update',
                'event_type': event_type,
                'data': data
            }
        )
    
    @staticmethod
    def notify_admin(admin_id, event_type, data):
        """Send real-time notification to admin"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'admin_{admin_id}',
            {
                'type': 'ticket_update',
                'event_type': event_type,
                'data': data
            }
        )
    
    @staticmethod
    def notify_all_admins(event_type, data):
        """Broadcast to all online admins"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'admins_online',
            {
                'type': 'ticket_update',
                'event_type': event_type,
                'data': data
            }
        )
    
    @staticmethod
    def broadcast_queue_update():
        """Broadcast queue status to all waiting users"""
        channel_layer = get_channel_layer()
        queue_manager = TicketQueueManager()
        
        async_to_sync(channel_layer.group_send)(
            'ticket_queue',
            {
                'type': 'queue_update',
                'queue_length': queue_manager.get_queue_length()
            }
        )


class EnhancedTicketService:
    """Enhanced ticket service with real-time support"""
    
    def __init__(self):
        self.queue_manager = TicketQueueManager()
        self.file_manager = FileUploadManager()
        self.notifier = TicketNotificationService()
    
    @transaction.atomic
    def create_ticket(self, user, subject, message, category='GENERAL', 
                     priority='MEDIUM', order_id=None, attachments=None):
        """Create ticket with real-time queue management"""
        try:
            ticket_number = self._generate_ticket_number()
            
            ticket = SupportTicket.objects.create(
                user_id=user,
                ticket_number=ticket_number,
                subject=subject,
                category=category,
                priority=priority,
                status='OPEN',
                order_id_id=order_id if order_id else None,
                queue_position=0
            )
            
            # Handle attachments
            attachment_urls = []
            if attachments:
                for file in attachments:
                    is_valid, error = self.file_manager.validate_file(file)
                    if is_valid:
                        attachment_urls.append(
                            self.file_manager.save_attachment(file, ticket.id)
                        )
            
            # Create initial message
            TicketMessage.objects.create(
                ticket_id=ticket,
                user_id=user,
                message_type='USER',
                message=message,
                attachments=attachment_urls
            )
            
            # Try auto-assign or add to queue
            assigned = self._try_auto_assign(ticket)
            
            if not assigned:
                position = self.queue_manager.add_to_queue(ticket.id, priority)
                ticket.queue_position = position
                ticket.save(update_fields=['queue_position'])
                
                # Notify user of queue position
                self.notifier.notify_user(user.id, 'ticket_queued', {
                    'ticket_id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'queue_position': position,
                    'estimated_wait': position * 5
                })
            
            # Notify admins of new ticket
            self.notifier.notify_all_admins('new_ticket', {
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'priority': priority,
                'category': category
            })
            
            return {
                'success': True,
                'message': 'Ticket created successfully',
                'ticket': {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'status': ticket.status,
                    'queue_position': position if not assigned else 0,
                    'assigned': assigned
                }
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to create ticket: {str(e)}'}
    
    def get_user_tickets(self, user, page=1, per_page=20, status=None):
        """Get user tickets with caching"""
        cache_key = f'user_tickets_{user.id}_{status}_{page}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        queryset = SupportTicket.objects.filter(user_id=user).select_related(
            'assigned_to'
        ).prefetch_related('messages')
        
        if status:
            queryset = queryset.filter(status=status)
        
        queryset = queryset.order_by('-created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        tickets = []
        for ticket in page_obj.object_list:
            # Get live queue position if in queue
            queue_position = 0
            if ticket.queue_position > 0:
                queue_position = self.queue_manager.get_position(ticket.id)
            
            last_message = ticket.messages.order_by('-created_at').first()
            
            tickets.append({
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'subject': ticket.subject,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'assigned_to': {
                    'name': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}"
                } if ticket.assigned_to else None,
                'queue_position': queue_position,
                'last_message': {
                    'message': last_message.message[:100],
                    'created_at': last_message.created_at.isoformat()
                } if last_message else None,
                'unread_count': self._get_unread_count(ticket, user),
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat()
            })
        
        result = {
            'success': True,
            'tickets': tickets,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_tickets': paginator.count
            }
        }
        
        cache.set(cache_key, result, 300)  # Cache for 5 minutes
        return result
    
    @transaction.atomic
    def add_message(self, user, ticket_id, message, attachments=None):
        """Add message with real-time delivery"""
        try:
            ticket = SupportTicket.objects.select_related('assigned_to').get(
                id=ticket_id, user_id=user
            )
            
            if ticket.status == 'CLOSED':
                return {'success': False, 'message': 'Cannot reply to closed ticket'}
            
            # Handle attachments
            attachment_urls = []
            if attachments:
                for file in attachments:
                    is_valid, error = self.file_manager.validate_file(file)
                    if is_valid:
                        attachment_urls.append(
                            self.file_manager.save_attachment(file, ticket.id)
                        )
            
            # Create message
            msg = TicketMessage.objects.create(
                ticket_id=ticket,
                user_id=user,
                message_type='USER',
                message=message,
                attachments=attachment_urls
            )
            
            # Update ticket status
            if ticket.status == 'PENDING':
                ticket.status = 'WAITING'
                ticket.save(update_fields=['status'])
            
            ticket.updated_at = timezone.now()
            ticket.save(update_fields=['updated_at'])
            
            # Real-time notification to admin
            if ticket.assigned_to:
                self.notifier.notify_admin(ticket.assigned_to.id, 'new_message', {
                    'ticket_id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'message': message,
                    'attachments': attachment_urls,
                    'from_user': f"{user.first_name} {user.last_name}",
                    'created_at': msg.created_at.isoformat()
                })
            
            return {
                'success': True,
                'message': 'Message sent successfully',
                'message_data': {
                    'id': msg.id,
                    'message': msg.message,
                    'attachments': msg.attachments,
                    'created_at': msg.created_at.isoformat()
                }
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @transaction.atomic
    def take_ticket(self, admin_user, ticket_id):
        """Admin takes ticket from queue"""
        try:
            ticket = SupportTicket.objects.select_related('user_id').get(id=ticket_id)
            
            if ticket.assigned_to:
                return {'success': False, 'message': 'Ticket is already assigned'}
            
            # Check admin availability
            availability = self._check_admin_availability(admin_user)
            if not availability['can_accept']:
                return {'success': False, 'message': 'You have reached maximum ticket limit'}
            
            # Remove from queue
            self.queue_manager.remove_from_queue(ticket.id)
            self.queue_manager.mark_ticket_active(ticket.id, admin_user.id)
            
            # Update ticket
            ticket.assigned_to = admin_user
            ticket.queue_position = 0
            ticket.status = 'IN_PROGRESS'
            ticket.save()
            
            self._update_admin_ticket_count(admin_user, 1)
            
            TicketAssignment.objects.create(
                ticket_id=ticket,
                assigned_to=admin_user,
                assigned_by=admin_user,
                reason='Self-assigned from queue'
            )
            
            # Notify user
            self.notifier.notify_user(ticket.user_id.id, 'ticket_assigned', {
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'admin_name': f"{admin_user.first_name} {admin_user.last_name}"
            })
            
            # Update queue for other waiting users
            self.notifier.broadcast_queue_update()
            
            return {
                'success': True,
                'message': 'Ticket assigned to you',
                'ticket': {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'user': {
                        'name': f"{ticket.user_id.first_name} {ticket.user_id.last_name}",
                        'email': ticket.user_id.email
                    }
                }
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @transaction.atomic
    def reply_to_ticket(self, admin_user, ticket_id, message, internal=False, attachments=None):
        """Admin reply with real-time delivery"""
        try:
            ticket = SupportTicket.objects.select_related('user_id').get(id=ticket_id)
            
            # Handle attachments
            attachment_urls = []
            if attachments:
                for file in attachments:
                    is_valid, error = self.file_manager.validate_file(file)
                    if is_valid:
                        attachment_urls.append(
                            self.file_manager.save_attachment(file, ticket.id)
                        )
            
            msg = TicketMessage.objects.create(
                ticket_id=ticket,
                user_id=admin_user,
                message_type='NOTE' if internal else 'ADMIN',
                message=message,
                is_internal=internal,
                attachments=attachment_urls
            )
            
            if not ticket.first_response_at and not internal:
                ticket.first_response_at = timezone.now()
            
            if not internal:
                ticket.status = 'PENDING'
                
                # Real-time notification to user
                self.notifier.notify_user(ticket.user_id.id, 'admin_reply', {
                    'ticket_id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'message': message,
                    'attachments': attachment_urls,
                    'admin_name': f"{admin_user.first_name} {admin_user.last_name}",
                    'created_at': msg.created_at.isoformat()
                })
            
            ticket.updated_at = timezone.now()
            ticket.save()
            
            return {
                'success': True,
                'message': 'Reply sent successfully',
                'message_data': {
                    'id': msg.id,
                    'message': msg.message,
                    'attachments': msg.attachments,
                    'created_at': msg.created_at.isoformat()
                }
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @transaction.atomic
    def close_ticket(self, user, ticket_id, rating=None, feedback=None):
        """User closes ticket with optional feedback"""
        try:
            ticket = SupportTicket.objects.select_related('assigned_to').get(
                id=ticket_id, 
                user_id=user
            )
            
            if ticket.status == 'CLOSED':
                return {'success': False, 'message': 'Ticket is already closed'}
            
            old_status = ticket.status
            ticket.status = 'CLOSED'
            ticket.closed_at = timezone.now()
            
            if rating:
                ticket.rating = rating
            if feedback:
                ticket.feedback = feedback
            
            ticket.save()
            
            # Create status history
            TicketStatusHistory.objects.create(
                ticket_id=ticket,
                from_status=old_status,
                to_status='CLOSED',
                changed_by=user,
                reason='Closed by user'
            )
            
            # Update admin ticket count
            if ticket.assigned_to:
                self._update_admin_ticket_count(ticket.assigned_to, -1)
            
            # Remove from active tickets
            self.queue_manager.unmark_ticket_active(ticket.id)
            
            # Notify admin
            if ticket.assigned_to:
                self.notifier.notify_admin(ticket.assigned_to.id, 'ticket_closed', {
                    'ticket_id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'rating': rating,
                    'feedback': feedback
                })
            
            return {
                'success': True,
                'message': 'Ticket closed successfully'
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    def get_queue_position(self, user, ticket_id):
        """Get current queue position for user's ticket"""
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user_id=user)
            
            if ticket.queue_position == 0:
                return {
                    'success': True,
                    'message': 'Ticket is assigned to an admin',
                    'queue_position': 0,
                    'assigned_to': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}" if ticket.assigned_to else None
                }
            
            # Get live position from Redis
            position = self.queue_manager.get_position(ticket.id)
            
            return {
                'success': True,
                'queue_position': position,
                'estimated_wait_minutes': position * 5
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    def get_live_queue_stats(self):
        """Get real-time queue statistics"""
        return {
            'success': True,
            'stats': {
                'queue_length': self.queue_manager.get_queue_length(),
                'active_tickets': len(self.queue_manager.redis_client.hgetall(
                    self.queue_manager.active_tickets_key
                )),
                'available_admins': self._get_available_admins_count(),
                'average_wait_time': self._calculate_average_wait_time()
            }
        }
    
    def _try_auto_assign(self, ticket):
        """Try to auto-assign ticket to available admin"""
        available_admin = AdminAvailability.objects.filter(
            status='ONLINE',
            current_tickets__lt=F('max_tickets')
        ).select_related('admin_id').order_by('current_tickets').first()
        
        if available_admin:
            ticket.assigned_to = available_admin.admin_id
            ticket.queue_position = 0
            ticket.status = 'IN_PROGRESS'
            ticket.save()
            
            self.queue_manager.mark_ticket_active(ticket.id, available_admin.admin_id.id)
            
            available_admin.current_tickets += 1
            available_admin.save(update_fields=['current_tickets'])
            
            TicketAssignment.objects.create(
                ticket_id=ticket,
                assigned_to=available_admin.admin_id,
                assigned_by=None,
                reason='Auto-assigned'
            )
            
            # Notify user immediately
            self.notifier.notify_user(ticket.user_id.id, 'ticket_assigned', {
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'admin_name': f"{available_admin.admin_id.first_name} {available_admin.admin_id.last_name}"
            })
            
            return True
        
        return False
    
    def _check_admin_availability(self, admin):
        """Check if admin can accept more tickets"""
        availability, _ = AdminAvailability.objects.get_or_create(
            admin_id=admin,
            defaults={'max_tickets': 10, 'current_tickets': 0}
        )
        
        return {
            'can_accept': availability.current_tickets < availability.max_tickets,
            'current_tickets': availability.current_tickets,
            'max_tickets': availability.max_tickets
        }
    
    def _get_unread_count(self, ticket, user):
        """Get unread messages count for user"""
        cache_key = f'unread_count_{ticket.id}_{user.id}'
        count = cache.get(cache_key)
        
        if count is None:
            count = TicketMessage.objects.filter(
                ticket_id=ticket,
                is_internal=False
            ).exclude(user_id=user).count()
            cache.set(cache_key, count, 300)
        
        return count
    
    def _get_available_admins_count(self):
        """Get count of available admins"""
        return AdminAvailability.objects.filter(
            status='ONLINE',
            current_tickets__lt=F('max_tickets')
        ).count()
    
    def _calculate_average_wait_time(self):
        """Calculate average wait time in minutes"""
        recent_tickets = SupportTicket.objects.filter(
            first_response_at__isnull=False,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).annotate(
            wait_time=F('first_response_at') - F('created_at')
        )
        
        if recent_tickets.exists():
            avg_seconds = sum([
                t.wait_time.total_seconds() for t in recent_tickets
            ]) / recent_tickets.count()
            return int(avg_seconds / 60)
        
        return 5  # Default 5 minutes
    
    @staticmethod
    def _generate_ticket_number():
        """Generate unique ticket number"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(3).upper()
        return f"TKT-{timestamp}-{random_part}"
    
    def get_my_tickets_admin(self, admin_user, page=1, per_page=20, status=None):
        """Get tickets assigned to admin"""
        queryset = SupportTicket.objects.filter(
            assigned_to=admin_user
        ).select_related('user_id')
        
        if status:
            queryset = queryset.filter(status=status)
        
        queryset = queryset.order_by('-priority', 'created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        tickets = [
            {
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'user': {
                    'email': ticket.user_id.email,
                    'name': f"{ticket.user_id.first_name} {ticket.user_id.last_name}"
                },
                'subject': ticket.subject,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat()
            }
            for ticket in page_obj.object_list
        ]
        
        return {
            'success': True,
            'tickets': tickets,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_tickets': paginator.count
            }
        }
    
    def get_all_tickets_admin(self, page=1, per_page=20, filters=None):
        """Get all tickets with filters for admin"""
        queryset = SupportTicket.objects.select_related(
            'user_id',
            'assigned_to'
        ).all()
        
        if filters:
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            if filters.get('priority'):
                queryset = queryset.filter(priority=filters['priority'])
            if filters.get('category'):
                queryset = queryset.filter(category=filters['category'])
            if filters.get('assigned_to'):
                queryset = queryset.filter(assigned_to=filters['assigned_to'])
            if filters.get('unassigned'):
                queryset = queryset.filter(assigned_to__isnull=True)
        
        queryset = queryset.order_by('-priority', 'created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        tickets = [
            {
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'user': {
                    'id': ticket.user_id.id,
                    'email': ticket.user_id.email,
                    'name': f"{ticket.user_id.first_name} {ticket.user_id.last_name}"
                },
                'subject': ticket.subject,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'assigned_to': {
                    'id': ticket.assigned_to.id,
                    'name': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}"
                } if ticket.assigned_to else None,
                'queue_position': self.queue_manager.get_position(ticket.id) if ticket.queue_position > 0 else 0,
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat()
            }
            for ticket in page_obj.object_list
        ]
        
        return {
            'success': True,
            'tickets': tickets,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_tickets': paginator.count
            }
        }
    
    @transaction.atomic
    def assign_ticket(self, admin_user, ticket_id, assign_to_id):
        """Assign ticket to another admin"""
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            assign_to = User.objects.get(id=assign_to_id, role='ADMIN')
            
            old_assigned = ticket.assigned_to
            ticket.assigned_to = assign_to
            ticket.queue_position = 0
            ticket.save(update_fields=['assigned_to', 'queue_position'])
            
            # Update ticket counts
            if old_assigned:
                self._update_admin_ticket_count(old_assigned, -1)
            self._update_admin_ticket_count(assign_to, 1)
            
            # Remove from queue if it was there
            self.queue_manager.remove_from_queue(ticket.id)
            self.queue_manager.mark_ticket_active(ticket.id, assign_to.id)
            
            TicketAssignment.objects.create(
                ticket_id=ticket,
                assigned_from=old_assigned,
                assigned_to=assign_to,
                assigned_by=admin_user
            )
            
            # Notify the admin being assigned
            self.notifier.notify_admin(assign_to.id, 'ticket_assigned', {
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'assigned_by': f"{admin_user.first_name} {admin_user.last_name}"
            })
            
            return {
                'success': True,
                'message': f'Ticket assigned to {assign_to.first_name} {assign_to.last_name}'
            }
            
        except (SupportTicket.DoesNotExist, User.DoesNotExist):
            return {'success': False, 'message': 'Ticket or user not found'}
    
    @transaction.atomic
    def update_ticket_status_admin(self, admin_user, ticket_id, new_status, reason=None):
        """Update ticket status"""
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            old_status = ticket.status
            
            ticket.status = new_status
            
            if new_status == 'RESOLVED':
                ticket.resolved_at = timezone.now()
            elif new_status == 'CLOSED':
                ticket.closed_at = timezone.now()
                if ticket.assigned_to:
                    self._update_admin_ticket_count(ticket.assigned_to, -1)
                self.queue_manager.unmark_ticket_active(ticket.id)
            
            ticket.save()

            TicketStatusHistory.objects.create(
                ticket_id=ticket,
                from_status=old_status,
                to_status=new_status,
                changed_by=admin_user,
                reason=reason
            )
            
            # Notify user of status change
            self.notifier.notify_user(ticket.user_id.id, 'status_changed', {
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'old_status': old_status,
                'new_status': new_status
            })
            
            return {
                'success': True,
                'message': 'Status updated successfully'
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    def get_ticket_statistics_admin(self):
        """Get ticket statistics for admin dashboard"""
        stats = SupportTicket.objects.aggregate(
            total=Count('id'),
            open=Count('id', filter=Q(status='OPEN')),
            in_progress=Count('id', filter=Q(status='IN_PROGRESS')),
            pending=Count('id', filter=Q(status='PENDING')),
            resolved=Count('id', filter=Q(status='RESOLVED')),
            closed=Count('id', filter=Q(status='CLOSED')),
            unassigned=Count('id', filter=Q(assigned_to__isnull=True)),
            avg_rating=Avg('rating', filter=Q(rating__isnull=False))
        )
        
        return {
            'success': True,
            'stats': {
                'total_tickets': stats['total'] or 0,
                'open': stats['open'] or 0,
                'in_progress': stats['in_progress'] or 0,
                'pending': stats['pending'] or 0,
                'resolved': stats['resolved'] or 0,
                'closed': stats['closed'] or 0,
                'unassigned': stats['unassigned'] or 0,
                'average_rating': round(float(stats['avg_rating'] or 0), 2),
                'queue_length': self.queue_manager.get_queue_length(),
                'active_tickets': len(self.queue_manager.redis_client.hgetall(
                    self.queue_manager.active_tickets_key
                ))
            }
        }

    @staticmethod
    def _update_admin_ticket_count(admin, delta):
        """Update admin's active ticket count"""
        availability, created = AdminAvailability.objects.get_or_create(
            admin_id=admin,
            defaults={'current_tickets': 0, 'max_tickets': 10}
        )
        
        availability.current_tickets = F('current_tickets') + delta
        availability.save(update_fields=['current_tickets'])
        availability.refresh_from_db()


# Initialize service
ticket_service = EnhancedTicketService()