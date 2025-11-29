import secrets
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from users.models import Order, Service, User, Cart, CartItem


class OrderService:
    
    @staticmethod
    @transaction.atomic
    def create_orders_from_cart(user, payment_transaction_id):
        try:
            cart = Cart.objects.prefetch_related('items__service_id').get(
                user_id=user,
                status='ACTIVE'
            )
            
            if cart.total_items == 0:
                return {'success': False, 'message': 'Cart is empty'}
            
            orders = []
            
            for item in cart.items.all():
                service = item.service_id
                
                order_number = OrderService._generate_order_number()
                
                price_paid = item.total_amount
                supplier_cost = (Decimal(item.quantity) / 100) * service.supplier_price_per_100
                profit = price_paid - supplier_cost
                
                order = Order.objects.create(
                    user_id=user,
                    service_id=service,
                    order_number=order_number,
                    link=item.link,
                    quantity=item.quantity,
                    price_paid=price_paid,
                    profit=profit,
                    status='PENDING',
                    start_count=0,
                    remains=item.quantity,
                    customer_note=item.notes or ''
                )
                
                orders.append(order)
                
                service.total_orders += 1
                service.save()
            
            cart.status = 'CONVERTED'
            cart.converted_at = timezone.now()
            cart.save()
            
            CartItem.objects.filter(cart_id=cart).delete()
            
            return {
                'success': True,
                'orders': [o.order_number for o in orders],
                'total_orders': len(orders),
                'message': 'Orders created successfully'
            }
            
        except Cart.DoesNotExist:
            return {'success': False, 'message': 'Cart not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create orders: {str(e)}'}
    
    @staticmethod
    def get_user_orders(user, page=1, per_page=20, status=None):
        queryset = Order.objects.filter(user_id=user).select_related('service_id').order_by('-submitted_at')
        
        if status:
            queryset = queryset.filter(status=status)
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        orders = []
        for order in page_obj.object_list:
            orders.append({
                'id': order.id,
                'order_number': order.order_number,
                'service': {
                    'id': order.service_id.id,
                    'name': order.service_id.name,
                    'photo': order.service_id.photo.url if order.service_id.photo else None
                },
                'link': order.link,
                'quantity': order.quantity,
                'price_paid': float(order.price_paid),
                'status': order.status,
                'start_count': order.start_count,
                'remains': order.remains,
                'submitted_at': order.submitted_at.isoformat(),
                'completed_at': order.completed_at.isoformat() if order.completed_at else None
            })
        
        return {
            'success': True,
            'orders': orders,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_orders': paginator.count
            }
        }
    
    @staticmethod
    def get_order_by_number(user, order_number):
        try:
            order = Order.objects.select_related('service_id__category_id').get(
                order_number=order_number,
                user_id=user
            )
            
            return {
                'success': True,
                'order': {
                    'id': order.id,
                    'order_number': order.order_number,
                    'service': {
                        'id': order.service_id.id,
                        'name': order.service_id.name,
                        'category': order.service_id.category_id.name
                    },
                    'link': order.link,
                    'quantity': order.quantity,
                    'price_paid': float(order.price_paid),
                    'status': order.status,
                    'start_count': order.start_count,
                    'remains': order.remains,
                    'customer_note': order.customer_note,
                    'submitted_at': order.submitted_at.isoformat(),
                    'completed_at': order.completed_at.isoformat() if order.completed_at else None
                }
            }
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}
    
    @staticmethod
    @transaction.atomic
    def update_order_status(order_id, status, start_count=None, remains=None):
        try:
            order = Order.objects.select_related('service_id').get(id=order_id)
            
            order.status = status
            
            if start_count is not None:
                order.start_count = start_count
            
            if remains is not None:
                order.remains = remains
            
            if status == 'COMPLETED':
                order.completed_at = timezone.now()
                order.service_id.total_completed += 1
                order.service_id.save()
            
            order.save()
            
            return {'success': True, 'message': 'Order status updated'}
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}
    
    @staticmethod
    def get_order_stats(user):
        from django.db.models import Count, Sum
        from django.db import models
        
        stats = Order.objects.filter(user_id=user).aggregate(
            total_orders=Count('id'),
            pending=Count('id', filter=models.Q(status='PENDING')),
            processing=Count('id', filter=models.Q(status='PROCESSING')),
            completed=Count('id', filter=models.Q(status='COMPLETED')),
            total_spent=Sum('price_paid')
        )
        
        return {
            'success': True,
            'stats': {
                'total_orders': stats['total_orders'] or 0,
                'pending_orders': stats['pending'] or 0,
                'processing_orders': stats['processing'] or 0,
                'completed_orders': stats['completed'] or 0,
                'total_spent': float(stats['total_spent'] or 0)
            }
        }
    
    @staticmethod
    def _generate_order_number():
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(4).upper()
        return f"ORD-{timestamp}-{random_part}"