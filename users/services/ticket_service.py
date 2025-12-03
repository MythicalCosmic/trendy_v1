import secrets
from django.db import transaction, models
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from users.models import (
    SupportTicket, TicketMessage, TicketAssignment,
    TicketStatusHistory, AdminAvailability, User
)


class TicketService:
    @staticmethod
    @transaction.atomic
    def create_ticket(user, subject, message, category='GENERAL', priority='MEDIUM', order_id=None):
        try:
            ticket_number = TicketService._generate_ticket_number()
            
            ticket = SupportTicket.objects.create(
                user_id=user,
                ticket_number=ticket_number,
                subject=subject,
                category=category,
                priority=priority,
                status='OPEN',
                order_id_id=order_id if order_id else None,
                queue_position=TicketService._get_next_queue_position()
            )
            
            TicketMessage.objects.create(
                ticket_id=ticket,
                user_id=user,
                message_type='USER',
                message=message
            )
            
            TicketService._try_auto_assign(ticket)
            
            return {
                'success': True,
                'message': 'Ticket created successfully',
                'ticket': {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'status': ticket.status,
                    'queue_position': ticket.queue_position if ticket.queue_position > 0 else None
                }
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to create ticket: {str(e)}'}
    
    @staticmethod
    def get_user_tickets(user, page=1, per_page=20, status=None):
        queryset = SupportTicket.objects.filter(user_id=user).select_related(
            'assigned_to'
        )
        
        if status:
            queryset = queryset.filter(status=status)
        
        queryset = queryset.order_by('-created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        tickets = [
            {
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'subject': ticket.subject,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'assigned_to': {
                    'name': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}"
                } if ticket.assigned_to else None,
                'queue_position': ticket.queue_position if ticket.queue_position > 0 else None,
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
    
    @staticmethod
    def get_ticket_details(user, ticket_id):
        try:
            ticket = SupportTicket.objects.select_related(
                'user_id',
                'assigned_to',
                'order_id'
            ).get(id=ticket_id, user_id=user)
            
            messages = TicketMessage.objects.filter(
                ticket_id=ticket,
                is_internal=False
            ).select_related('user_id').order_by('created_at')
            
            return {
                'success': True,
                'ticket': {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'subject': ticket.subject,
                    'category': ticket.category,
                    'priority': ticket.priority,
                    'status': ticket.status,
                    'assigned_to': {
                        'name': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}",
                        'email': ticket.assigned_to.email
                    } if ticket.assigned_to else None,
                    'order': {
                        'order_number': ticket.order_id.order_number,
                        'service': ticket.order_id.service_id.name
                    } if ticket.order_id else None,
                    'queue_position': ticket.queue_position if ticket.queue_position > 0 else None,
                    'created_at': ticket.created_at.isoformat(),
                    'updated_at': ticket.updated_at.isoformat(),
                    'messages': [
                        {
                            'id': msg.id,
                            'user': {
                                'name': f"{msg.user_id.first_name} {msg.user_id.last_name}",
                                'role': msg.user_id.role
                            } if msg.user_id else {'name': 'System', 'role': 'SYSTEM'},
                            'message_type': msg.message_type,
                            'message': msg.message,
                            'created_at': msg.created_at.isoformat()
                        }
                        for msg in messages
                    ]
                }
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @staticmethod
    @transaction.atomic
    def add_message(user, ticket_id, message):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user_id=user)
            
            if ticket.status == 'CLOSED':
                return {'success': False, 'message': 'Cannot reply to closed ticket'}
            
            TicketMessage.objects.create(
                ticket_id=ticket,
                user_id=user,
                message_type='USER',
                message=message
            )
            
            if ticket.status == 'PENDING':
                ticket.status = 'WAITING'
                ticket.save(update_fields=['status'])
            
            ticket.updated_at = timezone.now()
            ticket.save(update_fields=['updated_at'])
            
            return {
                'success': True,
                'message': 'Message sent successfully'
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @staticmethod
    @transaction.atomic
    def close_ticket(user, ticket_id, rating=None, feedback=None):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user_id=user)
            
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
            
            TicketStatusHistory.objects.create(
                ticket_id=ticket,
                from_status=old_status,
                to_status='CLOSED',
                changed_by=user,
                reason='Closed by user'
            )
            
            if ticket.assigned_to:
                TicketService._update_admin_ticket_count(ticket.assigned_to, -1)
            
            return {
                'success': True,
                'message': 'Ticket closed successfully'
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @staticmethod
    def get_queue_position(user, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user_id=user)
            
            if ticket.queue_position == 0:
                return {
                    'success': True,
                    'message': 'Ticket is assigned to an admin',
                    'queue_position': 0,
                    'assigned_to': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}" if ticket.assigned_to else None
                }
            
            return {
                'success': True,
                'queue_position': ticket.queue_position,
                'estimated_wait_minutes': ticket.queue_position * 5 
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}

    @staticmethod
    def get_all_tickets_admin(page=1, per_page=20, filters=None):
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
                'queue_position': ticket.queue_position,
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
    
    @staticmethod
    def get_my_tickets_admin(admin_user, page=1, per_page=20, status=None):
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
    
    @staticmethod
    @transaction.atomic
    def assign_ticket(admin_user, ticket_id, assign_to_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            assign_to = User.objects.get(id=assign_to_id, role='ADMIN')
            
            old_assigned = ticket.assigned_to
            ticket.assigned_to = assign_to
            ticket.queue_position = 0
            ticket.save(update_fields=['assigned_to', 'queue_position'])
  
            if old_assigned:
                TicketService._update_admin_ticket_count(old_assigned, -1)
            TicketService._update_admin_ticket_count(assign_to, 1)
            
            TicketAssignment.objects.create(
                ticket_id=ticket,
                assigned_from=old_assigned,
                assigned_to=assign_to,
                assigned_by=admin_user
            )
            
            return {
                'success': True,
                'message': f'Ticket assigned to {assign_to.first_name} {assign_to.last_name}'
            }
            
        except (SupportTicket.DoesNotExist, User.DoesNotExist):
            return {'success': False, 'message': 'Ticket or user not found'}
    
    @staticmethod
    @transaction.atomic
    def take_ticket(admin_user, ticket_id):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            
            if ticket.assigned_to:
                return {'success': False, 'message': 'Ticket is already assigned'}
            
            ticket.assigned_to = admin_user
            ticket.queue_position = 0
            ticket.status = 'IN_PROGRESS'
            ticket.save()

            TicketService._update_admin_ticket_count(admin_user, 1)

            TicketAssignment.objects.create(
                ticket_id=ticket,
                assigned_to=admin_user,
                assigned_by=admin_user,
                reason='Self-assigned from queue'
            )
            
            return {
                'success': True,
                'message': 'Ticket assigned to you'
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @staticmethod
    @transaction.atomic
    def reply_to_ticket(admin_user, ticket_id, message, internal=False):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            
            TicketMessage.objects.create(
                ticket_id=ticket,
                user_id=admin_user,
                message_type='NOTE' if internal else 'ADMIN',
                message=message,
                is_internal=internal
            )
            
            if not ticket.first_response_at and not internal:
                ticket.first_response_at = timezone.now()
            
            if not internal:
                ticket.status = 'PENDING'
            
            ticket.updated_at = timezone.now()
            ticket.save()
            
            return {
                'success': True,
                'message': 'Reply sent successfully'
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @staticmethod
    @transaction.atomic
    def update_ticket_status_admin(admin_user, ticket_id, new_status, reason=None):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            old_status = ticket.status
            
            ticket.status = new_status
            
            if new_status == 'RESOLVED':
                ticket.resolved_at = timezone.now()
            elif new_status == 'CLOSED':
                ticket.closed_at = timezone.now()
                if ticket.assigned_to:
                    TicketService._update_admin_ticket_count(ticket.assigned_to, -1)
            
            ticket.save()

            TicketStatusHistory.objects.create(
                ticket_id=ticket,
                from_status=old_status,
                to_status=new_status,
                changed_by=admin_user,
                reason=reason
            )
            
            return {
                'success': True,
                'message': 'Status updated successfully'
            }
            
        except SupportTicket.DoesNotExist:
            return {'success': False, 'message': 'Ticket not found'}
    
    @staticmethod
    def get_ticket_statistics_admin():
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
                'average_rating': round(float(stats['avg_rating'] or 0), 2)
            }
        }
    
    @staticmethod
    def _generate_ticket_number():
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(3).upper()
        return f"TKT-{timestamp}-{random_part}"
    
    @staticmethod
    def _get_next_queue_position():
        max_position = SupportTicket.objects.filter(
            queue_position__gt=0
        ).aggregate(models.Max('queue_position'))['queue_position__max']
        
        return (max_position or 0) + 1
    
    @staticmethod
    def _try_auto_assign(ticket):
        available_admin = AdminAvailability.objects.filter(
            status='ONLINE',
            current_tickets__lt=F('max_tickets')
        ).select_related('admin_id').order_by('current_tickets').first()
        
        if available_admin:
            ticket.assigned_to = available_admin.admin_id
            ticket.queue_position = 0
            ticket.status = 'IN_PROGRESS'
            ticket.save()
            
            available_admin.current_tickets += 1
            available_admin.save(update_fields=['current_tickets'])
            
            TicketAssignment.objects.create(
                ticket_id=ticket,
                assigned_to=available_admin.admin_id,
                assigned_by=None,
                reason='Auto-assigned'
            )
    
    @staticmethod
    def _update_admin_ticket_count(admin, delta):
        availability, created = AdminAvailability.objects.get_or_create(
            admin_id=admin,
            defaults={'current_tickets': 0}
        )
        
        availability.current_tickets = F('current_tickets') + delta
        availability.save(update_fields=['current_tickets'])