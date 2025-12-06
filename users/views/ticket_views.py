# views/ticket_views.py
from rest_framework import status
from users.helpers.require_login import user_required
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from users.services import ticket_service
from users.services import ticket_service
from users.models import SupportTicket, User


@api_view(['POST'])
@user_required
def create_ticket(request):
    """
    Create a new support ticket with optional file attachments
    
    POST /api/tickets/create/
    JSON:
    {
        "subject": "Issue with order",
        "message": "Description of the issue",
        "category": "ORDER",
        "priority": "HIGH",
        "order_id": 123
    }
    
    OR Multipart (with files):
    FormData with fields + attachments[]
    """
    # Handle both JSON and multipart
    data = request.data
    files = request.FILES.getlist('attachments') if hasattr(request, 'FILES') else []
    
    # Validate required fields
    subject = data.get('subject', '').strip()
    message = data.get('message', '').strip()
    
    if not subject or not message:
        return Response({
            'success': False,
            'message': 'Subject and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    result = ticket_service.create_ticket(
        user=request.user,
        subject=subject,
        message=message,
        category=data.get('category', 'GENERAL'),
        priority=data.get('priority', 'MEDIUM'),
        order_id=data.get('order_id'),
        attachments=files if files else None
    )
    
    if result['success']:
        return Response(result, status=status.HTTP_201_CREATED)
    
    return Response(result, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@user_required
def get_my_tickets(request):
    """
    Get current user's tickets
    
    GET /api/tickets/my/?page=1&status=OPEN
    """
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    status_filter = request.GET.get('status')
    
    result = ticket_service.get_user_tickets(
        user=request.user,
        page=page,
        per_page=per_page,
        status=status_filter
    )
    
    return Response(result)


@api_view(['GET'])
@user_required
def get_ticket_details(request, ticket_id):
    """
    Get detailed ticket information
    
    GET /api/tickets/{ticket_id}/
    """
    try:
        ticket = get_object_or_404(
            SupportTicket.objects.select_related('user_id', 'assigned_to', 'order_id'),
            id=ticket_id
        )
        
        # Check permission
        if ticket.user_id != request.user and request.user.role != 'ADMIN':
            return Response({
                'success': False,
                'message': 'You do not have permission to view this ticket'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get messages
        messages = ticket.messages.filter(
            is_internal=False
        ).select_related('user_id').order_by('created_at')
        
        ticket_data = {
            'success': True,
            'ticket': {
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'subject': ticket.subject,
                'category': ticket.category,
                'priority': ticket.priority,
                'status': ticket.status,
                'user': {
                    'id': ticket.user_id.id,
                    'name': f"{ticket.user_id.first_name} {ticket.user_id.last_name}",
                    'email': ticket.user_id.email
                },
                'assigned_to': {
                    'id': ticket.assigned_to.id,
                    'name': f"{ticket.assigned_to.first_name} {ticket.assigned_to.last_name}",
                    'email': ticket.assigned_to.email
                } if ticket.assigned_to else None,
                'order': {
                    'id': ticket.order_id.id,
                    'order_number': ticket.order_id.order_number,
                    'service': ticket.order_id.service_id.name
                } if ticket.order_id else None,
                'queue_position': ticket_service.queue_manager.get_position(ticket.id) if ticket.queue_position > 0 else 0,
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat(),
                'first_response_at': ticket.first_response_at.isoformat() if ticket.first_response_at else None,
                'messages': [
                    {
                        'id': msg.id,
                        'user': {
                            'id': msg.user_id.id,
                            'name': f"{msg.user_id.first_name} {msg.user_id.last_name}",
                            'role': msg.user_id.role
                        } if msg.user_id else {'name': 'System', 'role': 'SYSTEM'},
                        'message_type': msg.message_type,
                        'message': msg.message,
                        'attachments': msg.attachments,
                        'created_at': msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            }
        }
        
        return Response(ticket_data)
        
    except SupportTicket.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Ticket not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@user_required
def add_message(request, ticket_id):
    """
    Add message to ticket with optional file attachments
    
    POST /api/tickets/{ticket_id}/message/
    JSON:
    {
        "message": "My message here"
    }
    
    OR Multipart (with files):
    FormData with message + attachments[]
    """
    message = request.data.get('message', '').strip()
    files = request.FILES.getlist('attachments') if hasattr(request, 'FILES') else []
    
    if not message:
        return Response({
            'success': False,
            'message': 'Message cannot be empty'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    result = ticket_service.add_message(
        user=request.user,
        ticket_id=ticket_id,
        message=message,
        attachments=files if files else None
    )
    
    if result['success']:
        return Response(result, status=status.HTTP_201_CREATED)
    
    return Response(result, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@user_required
def close_ticket(request, ticket_id):
    """
    Close ticket with optional feedback
    
    POST /api/tickets/{ticket_id}/close/
    {
        "rating": 5,
        "feedback": "Great support!"
    }
    """
    rating = request.data.get('rating')
    feedback = request.data.get('feedback')
    
    result = ticket_service.close_ticket(
        user=request.user,
        ticket_id=ticket_id,
        rating=rating,
        feedback=feedback
    )
    
    return Response(result)


@api_view(['GET'])
@user_required
def get_queue_position(request, ticket_id):
    """
    Get current queue position for a ticket
    
    GET /api/tickets/{ticket_id}/queue/
    """
    result = ticket_service.get_queue_position(request.user, ticket_id)
    return Response(result)


@api_view(['GET'])
@user_required
def get_queue_stats(request):
    """
    Get live queue statistics
    
    GET /api/tickets/queue/stats/
    """
    result = ticket_service.get_live_queue_stats()
    return Response(result)


# Admin endpoints

@api_view(['GET'])
@user_required
def admin_get_all_tickets(request):
    """
    Admin: Get all tickets with filters
    
    GET /api/admin/tickets/?page=1&status=OPEN&priority=HIGH
    """
    if request.user.role != 'ADMIN':
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    filters = {}
    if request.GET.get('status'):
        filters['status'] = request.GET.get('status')
    if request.GET.get('priority'):
        filters['priority'] = request.GET.get('priority')
    if request.GET.get('category'):
        filters['category'] = request.GET.get('category')
    if request.GET.get('unassigned') == 'true':
        filters['unassigned'] = True
    
    # ✅ Use the instance directly
    result = ticket_service.get_all_tickets_admin(
        page=page,
        per_page=per_page,
        filters=filters
    )
    
    return Response(result)


@api_view(['GET'])
@user_required
def admin_get_my_tickets(request):
    """
    Admin: Get assigned tickets
    
    GET /api/admin/tickets/my/?page=1&status=IN_PROGRESS
    """
    if request.user.role != 'ADMIN':
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    status_filter = request.GET.get('status')
    
    # ✅ Use the instance directly
    result = ticket_service.get_my_tickets_admin(
        admin_user=request.user,
        page=page,
        per_page=per_page,
        status=status_filter
    )
    
    return Response(result)


@api_view(['POST'])
@user_required
def admin_take_ticket(request, ticket_id):
    """
    Admin: Take ticket from queue
    
    POST /api/admin/tickets/{ticket_id}/take/
    """
    if request.user.role != 'ADMIN':
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    result = ticket_service.take_ticket(request.user, ticket_id)
    
    if result['success']:
        return Response(result)
    
    return Response(result, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@user_required
def admin_reply(request, ticket_id):
    """
    Admin: Reply to ticket with optional attachments
    
    POST /api/admin/tickets/{ticket_id}/reply/
    JSON:
    {
        "message": "Reply message",
        "internal": false
    }
    
    OR Multipart (with files):
    FormData with message, internal + attachments[]
    """
    if request.user.role != 'ADMIN':
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    message = request.data.get('message', '').strip()
    internal = request.data.get('internal', False)
    
    # Handle both string "true"/"false" and boolean
    if isinstance(internal, str):
        internal = internal.lower() == 'true'
    
    files = request.FILES.getlist('attachments') if hasattr(request, 'FILES') else []
    
    if not message:
        return Response({
            'success': False,
            'message': 'Message cannot be empty'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    result = ticket_service.reply_to_ticket(
        admin_user=request.user,
        ticket_id=ticket_id,
        message=message,
        internal=internal,
        attachments=files if files else None
    )
    
    if result['success']:
        return Response(result, status=status.HTTP_201_CREATED)
    
    return Response(result, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@user_required
def admin_update_status(request, ticket_id):
    """
    Admin: Update ticket status
    
    POST /api/admin/tickets/{ticket_id}/status/
    {
        "status": "RESOLVED",
        "reason": "Issue fixed"
    }
    """
    if request.user.role != 'ADMIN':
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    new_status = request.data.get('status')
    reason = request.data.get('reason')
    
    if not new_status:
        return Response({
            'success': False,
            'message': 'Status is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # ✅ Use the instance directly
    result = ticket_service.update_ticket_status_admin(
        admin_user=request.user,
        ticket_id=ticket_id,
        new_status=new_status,
        reason=reason
    )
    
    return Response(result)


@api_view(['POST'])
@user_required
def admin_assign_ticket(request, ticket_id):
    """
    Admin: Assign ticket to another admin
    
    POST /api/admin/tickets/{ticket_id}/assign/
    {
        "assign_to_id": 123
    }
    """
    if request.user.role != 'ADMIN':
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    assign_to_id = request.data.get('assign_to_id')
    
    if not assign_to_id:
        return Response({
            'success': False,
            'message': 'assign_to_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # ✅ Use the instance directly
    result = ticket_service.assign_ticket(
        admin_user=request.user,
        ticket_id=ticket_id,
        assign_to_id=assign_to_id
    )
    
    return Response(result)


@api_view(['GET'])
@user_required
def admin_statistics(request):
    """
    Admin: Get ticket statistics
    
    GET /api/admin/tickets/statistics/
    """
    if request.user.role != 'ADMIN':
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # ✅ Use the instance directly
    result = ticket_service.get_ticket_statistics_admin()
    return Response(result)


# URL Configuration
"""
# urls.py
from django.urls import path
from views import ticket_views

urlpatterns = [
    # User endpoints
    path('tickets/create/', ticket_views.create_ticket, name='create_ticket'),
    path('tickets/my/', ticket_views.get_my_tickets, name='my_tickets'),
    path('tickets/<int:ticket_id>/', ticket_views.get_ticket_details, name='ticket_details'),
    path('tickets/<int:ticket_id>/message/', ticket_views.add_message, name='add_message'),
    path('tickets/<int:ticket_id>/close/', ticket_views.close_ticket, name='close_ticket'),
    path('tickets/<int:ticket_id>/queue/', ticket_views.get_queue_position, name='queue_position'),
    path('tickets/queue/stats/', ticket_views.get_queue_stats, name='queue_stats'),
    
    # Admin endpoints
    path('admin/tickets/', ticket_views.admin_get_all_tickets, name='admin_all_tickets'),
    path('admin/tickets/my/', ticket_views.admin_get_my_tickets, name='admin_my_tickets'),
    path('admin/tickets/<int:ticket_id>/take/', ticket_views.admin_take_ticket, name='admin_take_ticket'),
    path('admin/tickets/<int:ticket_id>/reply/', ticket_views.admin_reply, name='admin_reply'),
    path('admin/tickets/<int:ticket_id>/status/', ticket_views.admin_update_status, name='admin_update_status'),
    path('admin/tickets/<int:ticket_id>/assign/', ticket_views.admin_assign_ticket, name='admin_assign_ticket'),
    path('admin/tickets/statistics/', ticket_views.admin_statistics, name='admin_statistics'),
]
"""