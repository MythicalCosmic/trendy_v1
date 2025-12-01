import secrets
from decimal import Decimal
from datetime import timedelta
from django.db import transaction, models
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Avg, Q, F, Prefetch
from django.core.cache import cache
from users.models import Order, Service, User, Cart, CartItem


class OrderService:
    CACHE_TTL = 300  

    @staticmethod
    @transaction.atomic
    def create_orders_from_cart(user, payment_transaction_id):
        try:
            cart = Cart.objects.prefetch_related(
                Prefetch('items', queryset=CartItem.objects.select_related('service_id'))
            ).get(user_id=user, status='ACTIVE')
            
            if cart.total_items == 0:
                return {'success': False, 'message': 'Cart is empty'}

            orders_to_create = []
            service_updates = {}
            cart_items = list(cart.items.all())
            
            for item in cart_items:
                service = item.service_id
                order_number = OrderService._generate_order_number()
                price_paid = item.total_amount
                supplier_cost = (Decimal(item.quantity) / 100) * service.supplier_price_per_100
                profit = price_paid - supplier_cost
                
                orders_to_create.append(Order(
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
                ))
                
                service_updates[service.id] = service_updates.get(service.id, 0) + 1
            
            created_orders = Order.objects.bulk_create(orders_to_create)
            
            for service_id, count in service_updates.items():
                Service.objects.filter(id=service_id).update(
                    total_orders=F('total_orders') + count
                )

            cart.status = 'CONVERTED'
            cart.converted_at = timezone.now()
            cart.save(update_fields=['status', 'converted_at'])
            

            CartItem.objects.filter(cart_id=cart).delete()
            
            cache.delete(f'user_orders_{user.id}')
            cache.delete(f'user_stats_{user.id}')
            
            return {
                'success': True,
                'orders': [o.order_number for o in created_orders],
                'total_orders': len(created_orders),
                'message': 'Orders created successfully'
            }
            
        except Cart.DoesNotExist:
            return {'success': False, 'message': 'Cart not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create orders: {str(e)}'}
    
    @staticmethod
    def get_user_orders(user, page=1, per_page=20, status=None):
        cache_key = f'user_orders_{user.id}_p{page}_s{status}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        queryset = Order.objects.filter(user_id=user).select_related('service_id').only(
            'id', 'order_number', 'link', 'quantity', 'price_paid', 'status',
            'start_count', 'remains', 'submitted_at', 'completed_at',
            'service_id__id', 'service_id__name', 'service_id__photo'
        ).order_by('-submitted_at')
        
        if status:
            queryset = queryset.filter(status=status)
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        orders = [
            {
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
            }
            for order in page_obj.object_list
        ]
        
        result = {
            'success': True,
            'orders': orders,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_orders': paginator.count
            }
        }
        
        cache.set(cache_key, result, OrderService.CACHE_TTL)
        return result
    
    @staticmethod
    def get_order_by_number(user, order_number):
        cache_key = f'order_{order_number}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            order = Order.objects.select_related('service_id__category_id').get(
                order_number=order_number,
                user_id=user
            )
            
            result = {
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
            
            cache.set(cache_key, result, OrderService.CACHE_TTL)
            return result
            
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}
    
    @staticmethod
    @transaction.atomic
    def update_order_status(order_id, status, start_count=None, remains=None):
        try:
            order = Order.objects.select_related('service_id').get(id=order_id)
            old_status = order.status
            
            order.status = status
            if start_count is not None:
                order.start_count = start_count
            if remains is not None:
                order.remains = remains
            
            if status == 'COMPLETED' and old_status != 'COMPLETED':
                order.completed_at = timezone.now()
                Service.objects.filter(id=order.service_id.id).update(
                    total_completed=F('total_completed') + 1
                )
            
            order.save()
            
            cache.delete(f'order_{order.order_number}')
            cache.delete(f'user_stats_{order.user_id.id}')
            
            return {'success': True, 'message': 'Order status updated'}
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}
    
    @staticmethod
    def get_order_stats(user):
        cache_key = f'user_stats_{user.id}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        stats = Order.objects.filter(user_id=user).aggregate(
            total_orders=Count('id'),
            pending=Count('id', filter=Q(status='PENDING')),
            processing=Count('id', filter=Q(status='PROCESSING')),
            completed=Count('id', filter=Q(status='COMPLETED')),
            total_spent=Sum('price_paid')
        )
        
        result = {
            'success': True,
            'stats': {
                'total_orders': stats['total_orders'] or 0,
                'pending_orders': stats['pending'] or 0,
                'processing_orders': stats['processing'] or 0,
                'completed_orders': stats['completed'] or 0,
                'total_spent': float(stats['total_spent'] or 0)
            }
        }
        
        cache.set(cache_key, result, OrderService.CACHE_TTL)
        return result
    
    
    @staticmethod
    def get_all_orders_admin(page=1, per_page=20, status=None, user_id=None, search=None, order_by='-submitted_at'):
        queryset = Order.objects.select_related(
            'user_id', 'service_id__category_id'
        ).only(
            'id', 'order_number', 'link', 'quantity', 'price_paid', 'profit',
            'status', 'start_count', 'remains', 'customer_note', 'admin_note',
            'submitted_at', 'completed_at',
            'user_id__id', 'user_id__email', 'user_id__first_name', 'user_id__last_name',
            'service_id__id', 'service_id__name', 'service_id__category_id__name'
        )
        

        if status:
            queryset = queryset.filter(status=status)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(link__icontains=search) |
                Q(user_id__email__icontains=search) |
                Q(service_id__name__icontains=search)
            )
        
        queryset = queryset.order_by(order_by)
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        orders = [
            {
                'id': order.id,
                'order_number': order.order_number,
                'user': {
                    'id': order.user_id.id,
                    'email': order.user_id.email,
                    'name': f"{order.user_id.first_name} {order.user_id.last_name}"
                },
                'service': {
                    'id': order.service_id.id,
                    'name': order.service_id.name,
                    'category': order.service_id.category_id.name
                },
                'link': order.link,
                'quantity': order.quantity,
                'price_paid': float(order.price_paid),
                'profit': float(order.profit),
                'status': order.status,
                'start_count': order.start_count,
                'remains': order.remains,
                'customer_note': order.customer_note,
                'admin_note': order.admin_note,
                'submitted_at': order.submitted_at.isoformat(),
                'completed_at': order.completed_at.isoformat() if order.completed_at else None
            }
            for order in page_obj.object_list
        ]
        
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
    def get_order_by_id_admin(order_id):
        try:
            order = Order.objects.select_related(
                'user_id', 'service_id__category_id'
            ).get(id=order_id)
            
            return {
                'success': True,
                'order': {
                    'id': order.id,
                    'order_number': order.order_number,
                    'user': {
                        'id': order.user_id.id,
                        'email': order.user_id.email,
                        'name': f"{order.user_id.first_name} {order.user_id.last_name}",
                        'phone': getattr(order.user_id, 'phone_number', None)
                    },
                    'service': {
                        'id': order.service_id.id,
                        'name': order.service_id.name,
                        'category': order.service_id.category_id.name,
                        'supplier_price': float(order.service_id.supplier_price_per_100)
                    },
                    'link': order.link,
                    'quantity': order.quantity,
                    'price_paid': float(order.price_paid),
                    'profit': float(order.profit),
                    'status': order.status,
                    'start_count': order.start_count,
                    'remains': order.remains,
                    'customer_note': order.customer_note,
                    'admin_note': order.admin_note,
                    'submitted_at': order.submitted_at.isoformat(),
                    'completed_at': order.completed_at.isoformat() if order.completed_at else None
                }
            }
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}
    
    @staticmethod
    @transaction.atomic
    def update_order_admin(order_id, **kwargs):
        try:
            order = Order.objects.select_related('service_id').get(id=order_id)
            old_status = order.status
            
            allowed_fields = ['status', 'start_count', 'remains', 'admin_note', 'link', 'quantity']
            update_fields = []
            
            for field, value in kwargs.items():
                if field in allowed_fields and value is not None:
                    setattr(order, field, value)
                    update_fields.append(field)

            if kwargs.get('status') == 'COMPLETED' and old_status != 'COMPLETED':
                order.completed_at = timezone.now()
                update_fields.append('completed_at')
                Service.objects.filter(id=order.service_id.id).update(
                    total_completed=F('total_completed') + 1
                )
            
            order.save(update_fields=update_fields)
            
            cache.delete(f'order_{order.order_number}')
            cache.delete(f'user_stats_{order.user_id.id}')
            cache.delete('admin_dashboard_stats')
            
            return {'success': True, 'message': 'Order updated successfully'}
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update order: {str(e)}'}
    
    @staticmethod
    @transaction.atomic
    def bulk_update_orders_admin(order_ids, **kwargs):
        try:
            if not order_ids:
                return {'success': False, 'message': 'No order IDs provided'}
            
            orders = Order.objects.filter(id__in=order_ids)
            
            if not orders.exists():
                return {'success': False, 'message': 'No orders found'}
            
            allowed_fields = ['status', 'start_count', 'remains', 'admin_note']
            update_data = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
            
            if kwargs.get('status') == 'COMPLETED':
                update_data['completed_at'] = timezone.now()

                service_counts = orders.exclude(status='COMPLETED').values('service_id').annotate(
                    count=Count('id')
                )
                
                for item in service_counts:
                    Service.objects.filter(id=item['service_id']).update(
                        total_completed=F('total_completed') + item['count']
                    )

            updated_count = orders.update(**update_data)
            
            cache.delete('admin_dashboard_stats')
            
            return {
                'success': True,
                'updated_count': updated_count,
                'message': f'Successfully updated {updated_count} orders'
            }
        except Exception as e:
            return {'success': False, 'message': f'Bulk update failed: {str(e)}'}
    
    @staticmethod
    @transaction.atomic
    def delete_order_admin(order_id):
        try:
            order = Order.objects.select_related('service_id').get(id=order_id)
            
            service = order.service_id
            Service.objects.filter(id=service.id).update(
                total_orders=F('total_orders') - 1
            )
            
            if order.status == 'COMPLETED':
                Service.objects.filter(id=service.id).update(
                    total_completed=F('total_completed') - 1
                )
            
            order_number = order.order_number
            user_id = order.user_id.id
            
            order.delete()
            
            cache.delete(f'order_{order_number}')
            cache.delete(f'user_stats_{user_id}')
            cache.delete('admin_dashboard_stats')
            
            return {
                'success': True,
                'message': f'Order {order_number} deleted successfully'
            }
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to delete order: {str(e)}'}
    
    @staticmethod
    @transaction.atomic
    def bulk_delete_orders_admin(order_ids):
        try:
            if not order_ids:
                return {'success': False, 'message': 'No order IDs provided'}
            
            orders = Order.objects.filter(id__in=order_ids).select_related('service_id')
            
            if not orders.exists():
                return {'success': False, 'message': 'No orders found'}
            
            service_stats = orders.values('service_id').annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='COMPLETED'))
            )

            for stat in service_stats:
                Service.objects.filter(id=stat['service_id']).update(
                    total_orders=F('total_orders') - stat['total'],
                    total_completed=F('total_completed') - stat['completed']
                )
            
            deleted_count = orders.count()
            orders.delete()
            
            cache.delete('admin_dashboard_stats')
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'message': f'Successfully deleted {deleted_count} orders'
            }
        except Exception as e:
            return {'success': False, 'message': f'Bulk delete failed: {str(e)}'}
    

    @staticmethod
    def get_admin_dashboard_stats():
        cache_key = 'admin_dashboard_stats'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        stats = Order.objects.aggregate(
            total_orders=Count('id'),
            pending=Count('id', filter=Q(status='PENDING')),
            processing=Count('id', filter=Q(status='PROCESSING')),
            completed=Count('id', filter=Q(status='COMPLETED')),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            partial=Count('id', filter=Q(status='PARTIAL')),
            failed=Count('id', filter=Q(status='FAILED')),
            total_revenue=Sum('price_paid'),
            total_profit=Sum('profit'),
            avg_order_value=Avg('price_paid'),
            
            today_orders=Count('id', filter=Q(submitted_at__gte=today_start)),
            today_revenue=Sum('price_paid', filter=Q(submitted_at__gte=today_start)),
            today_profit=Sum('profit', filter=Q(submitted_at__gte=today_start)),
            

            week_orders=Count('id', filter=Q(submitted_at__gte=week_start)),
            week_revenue=Sum('price_paid', filter=Q(submitted_at__gte=week_start)),
            week_profit=Sum('profit', filter=Q(submitted_at__gte=week_start)),
            
            month_orders=Count('id', filter=Q(submitted_at__gte=month_start)),
            month_revenue=Sum('price_paid', filter=Q(submitted_at__gte=month_start)),
            month_profit=Sum('profit', filter=Q(submitted_at__gte=month_start))
        )
        
        result = {
            'success': True,
            'stats': {
                'total': {
                    'orders': stats['total_orders'] or 0,
                    'revenue': float(stats['total_revenue'] or 0),
                    'profit': float(stats['total_profit'] or 0),
                    'avg_order_value': float(stats['avg_order_value'] or 0)
                },
                'by_status': {
                    'pending': stats['pending'] or 0,
                    'processing': stats['processing'] or 0,
                    'completed': stats['completed'] or 0,
                    'cancelled': stats['cancelled'] or 0,
                    'partial': stats['partial'] or 0,
                    'failed': stats['failed'] or 0
                },
                'today': {
                    'orders': stats['today_orders'] or 0,
                    'revenue': float(stats['today_revenue'] or 0),
                    'profit': float(stats['today_profit'] or 0)
                },
                'this_week': {
                    'orders': stats['week_orders'] or 0,
                    'revenue': float(stats['week_revenue'] or 0),
                    'profit': float(stats['week_profit'] or 0)
                },
                'this_month': {
                    'orders': stats['month_orders'] or 0,
                    'revenue': float(stats['month_revenue'] or 0),
                    'profit': float(stats['month_profit'] or 0)
                }
            }
        }
        
        cache.set(cache_key, result, OrderService.CACHE_TTL)
        return result
    
    @staticmethod
    def get_top_services_admin(limit=10, days=30):
        cutoff_date = timezone.now() - timedelta(days=days)
        
        top_services = Order.objects.filter(
            submitted_at__gte=cutoff_date
        ).values(
            'service_id__id', 'service_id__name', 'service_id__category_id__name'
        ).annotate(
            order_count=Count('id'),
            total_revenue=Sum('price_paid'),
            total_profit=Sum('profit')
        ).order_by('-order_count')[:limit]
        
        return {
            'success': True,
            'services': [
                {
                    'service_id': s['service_id__id'],
                    'service_name': s['service_id__name'],
                    'category': s['service_id__category_id__name'],
                    'order_count': s['order_count'],
                    'revenue': float(s['total_revenue'] or 0),
                    'profit': float(s['total_profit'] or 0)
                }
                for s in top_services
            ]
        }
    
    @staticmethod
    def get_top_customers_admin(limit=10, days=30):
        cutoff_date = timezone.now() - timedelta(days=days)
        
        top_customers = Order.objects.filter(
            submitted_at__gte=cutoff_date
        ).values(
            'user_id__id', 'user_id__email', 'user_id__first_name', 'user_id__last_name'
        ).annotate(
            order_count=Count('id'),
            total_spent=Sum('price_paid'),
            total_profit=Sum('profit')
        ).order_by('-total_spent')[:limit]
        
        return {
            'success': True,
            'customers': [
                {
                    'user_id': c['user_id__id'],
                    'email': c['user_id__email'],
                    'name': f"{c['user_id__first_name']} {c['user_id__last_name']}",
                    'order_count': c['order_count'],
                    'total_spent': float(c['total_spent'] or 0),
                    'profit_generated': float(c['total_profit'] or 0)
                }
                for c in top_customers
            ]
        }
    
    @staticmethod
    def get_recent_orders_admin(limit=10):
        recent_orders = Order.objects.select_related(
            'user_id', 'service_id'
        ).only(
            'id', 'order_number', 'quantity', 'price_paid', 'profit', 'status', 'submitted_at',
            'user_id__email', 'service_id__name'
        ).order_by('-submitted_at')[:limit]
        
        return {
            'success': True,
            'orders': [
                {
                    'id': order.id,
                    'order_number': order.order_number,
                    'user_email': order.user_id.email,
                    'service_name': order.service_id.name,
                    'quantity': order.quantity,
                    'price_paid': float(order.price_paid),
                    'profit': float(order.profit),
                    'status': order.status,
                    'submitted_at': order.submitted_at.isoformat()
                }
                for order in recent_orders
            ]
        }
    
    @staticmethod
    def get_revenue_by_period_admin(period='daily', start_date=None, end_date=None):
        from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
        
        queryset = Order.objects.filter(status='COMPLETED')
        
        if start_date:
            queryset = queryset.filter(submitted_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(submitted_at__lte=end_date)
        
        trunc_func = {
            'daily': TruncDay,
            'weekly': TruncWeek,
            'monthly': TruncMonth
        }.get(period, TruncDay)
        
        revenue_data = queryset.annotate(
            period=trunc_func('submitted_at')
        ).values('period').annotate(
            order_count=Count('id'),
            revenue=Sum('price_paid'),
            profit=Sum('profit')
        ).order_by('period')
        
        return {
            'success': True,
            'period': period,
            'data': [
                {
                    'period': item['period'].isoformat(),
                    'order_count': item['order_count'],
                    'revenue': float(item['revenue'] or 0),
                    'profit': float(item['profit'] or 0)
                }
                for item in revenue_data
            ]
        }
    @staticmethod
    def get_order_analytics_admin(start_date=None, end_date=None):
        from datetime import timedelta
        
        queryset = Order.objects.all()
        
        if start_date:
            queryset = queryset.filter(submitted_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(submitted_at__lte=end_date)
        
        overall_stats = queryset.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('price_paid'),
            total_profit=Sum('profit'),
            avg_order_value=Avg('price_paid'),
            pending=Count('id', filter=Q(status='PENDING')),
            processing=Count('id', filter=Q(status='PROCESSING')),
            completed=Count('id', filter=Q(status='COMPLETED')),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            partial=Count('id', filter=Q(status='PARTIAL')),
            failed=Count('id', filter=Q(status='FAILED'))
        )
        
        top_services = queryset.values(
            'service_id__id',
            'service_id__name'
        ).annotate(
            order_count=Count('id'),
            total_revenue=Sum('price_paid'),
            total_profit=Sum('profit')
        ).order_by('-order_count')[:10]
        
        top_customers = queryset.values(
            'user_id__id',
            'user_id__email',
            'user_id__first_name',
            'user_id__last_name'
        ).annotate(
            order_count=Count('id'),
            total_spent=Sum('price_paid')
        ).order_by('-total_spent')[:10]
        
        return {
            'success': True,
            'analytics': {
                'overall': {
                    'total_orders': overall_stats['total_orders'] or 0,
                    'total_revenue': float(overall_stats['total_revenue'] or 0),
                    'total_profit': float(overall_stats['total_profit'] or 0),
                    'avg_order_value': float(overall_stats['avg_order_value'] or 0),
                    'status_breakdown': {
                        'pending': overall_stats['pending'] or 0,
                        'processing': overall_stats['processing'] or 0,
                        'completed': overall_stats['completed'] or 0,
                        'cancelled': overall_stats['cancelled'] or 0,
                        'partial': overall_stats['partial'] or 0,
                        'failed': overall_stats['failed'] or 0
                    }
                },
                'top_services': [
                    {
                        'service_id': s['service_id__id'],
                        'service_name': s['service_id__name'],
                        'order_count': s['order_count'],
                        'total_revenue': float(s['total_revenue'] or 0),
                        'total_profit': float(s['total_profit'] or 0)
                    }
                    for s in top_services
                ],
                'top_customers': [
                    {
                        'user_id': c['user_id__id'],
                        'email': c['user_id__email'],
                        'name': f"{c['user_id__first_name']} {c['user_id__last_name']}",
                        'order_count': c['order_count'],
                        'total_spent': float(c['total_spent'] or 0)
                    }
                    for c in top_customers
                ]
            }
        }
    
    @staticmethod
    def get_pending_orders_count_admin():
        count = Order.objects.filter(status='PENDING').count()
        return {
            'success': True,
            'pending_count': count
        }
    
    @staticmethod
    def get_orders_by_service_admin(service_id, page=1, per_page=20):
        queryset = Order.objects.filter(
            service_id=service_id
        ).select_related('user_id').order_by('-submitted_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        orders = [
            {
                'id': order.id,
                'order_number': order.order_number,
                'user': {
                    'id': order.user_id.id,
                    'email': order.user_id.email
                },
                'quantity': order.quantity,
                'price_paid': float(order.price_paid),
                'profit': float(order.profit),
                'status': order.status,
                'submitted_at': order.submitted_at.isoformat()
            }
            for order in page_obj.object_list
        ]
        
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
    def get_user_order_history(user, page=1, per_page=20, filters=None):
        queryset = Order.objects.filter(user_id=user).select_related(
            'service_id__category_id'
        ).only(
            'id', 'order_number', 'link', 'quantity', 'price_paid', 
            'status', 'start_count', 'remains', 'submitted_at', 
            'completed_at', 'customer_note',
            'service_id__id', 'service_id__name', 'service_id__photo',
            'service_id__category_id__name'
        )
        
        if filters:
            if filters.get('status'):
                queryset = queryset.filter(status=filters['status'])
            
            if filters.get('service_id'):
                queryset = queryset.filter(service_id=filters['service_id'])
            
            if filters.get('date_from'):
                queryset = queryset.filter(submitted_at__gte=filters['date_from'])
            
            if filters.get('date_to'):
                queryset = queryset.filter(submitted_at__lte=filters['date_to'])
            
            if filters.get('search'):
                queryset = queryset.filter(
                    Q(order_number__icontains=filters['search']) |
                    Q(link__icontains=filters['search'])
                )
        
        queryset = queryset.order_by('-submitted_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        orders = [
            {
                'id': order.id,
                'order_number': order.order_number,
                'service': {
                    'id': order.service_id.id,
                    'name': order.service_id.name,
                    'category': order.service_id.category_id.name,
                    'photo': order.service_id.photo.url if order.service_id.photo else None
                },
                'link': order.link,
                'quantity': order.quantity,
                'price_paid': float(order.price_paid),
                'status': order.status,
                'progress': {
                    'start_count': order.start_count,
                    'remains': order.remains,
                    'delivered': order.quantity - order.remains if order.remains else order.quantity,
                    'percentage': round(((order.quantity - order.remains) / order.quantity * 100), 2) if order.quantity > 0 else 0
                },
                'customer_note': order.customer_note,
                'submitted_at': order.submitted_at.isoformat(),
                'completed_at': order.completed_at.isoformat() if order.completed_at else None,
                'estimated_completion': OrderService._estimate_completion(order)
            }
            for order in page_obj.object_list
        ]
        
        return {
            'success': True,
            'orders': orders,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_orders': paginator.count,
                'per_page': per_page
            }
        }


    @staticmethod
    def get_order_details(user, order_id):
        try:
            order = Order.objects.select_related(
                'service_id__category_id',
                'service_id__supplier_id'
            ).get(id=order_id, user_id=user)
            
            return {
                'success': True,
                'order': {
                    'id': order.id,
                    'order_number': order.order_number,
                    'supplier_order_id': order.supplier_order_id,
                    'service': {
                        'id': order.service_id.id,
                        'name': order.service_id.name,
                        'category': order.service_id.category_id.name,
                        'photo': order.service_id.photo.url if order.service_id.photo else None,
                        'average_time': order.service_id.average_time,
                        'refill_enabled': order.service_id.refill_enabled,
                        'cancel_enabled': order.service_id.cancel_enabled
                    },
                    'link': order.link,
                    'quantity': order.quantity,
                    'price_paid': float(order.price_paid),
                    'status': order.status,
                    'progress': {
                        'start_count': order.start_count,
                        'remains': order.remains,
                        'delivered': order.quantity - order.remains if order.remains else order.quantity,
                        'percentage': round(((order.quantity - order.remains) / order.quantity * 100), 2) if order.quantity > 0 else 0
                    },
                    'customer_note': order.customer_note,
                    'timeline': {
                        'submitted_at': order.submitted_at.isoformat(),
                        'completed_at': order.completed_at.isoformat() if order.completed_at else None,
                        'cancelled_at': order.cancelled_at.isoformat() if order.cancelled_at else None,
                        'refunded_at': order.refunded_at.isoformat() if order.refunded_at else None
                    },
                    'estimated_completion': OrderService._estimate_completion(order),
                    'can_cancel': order.status in ['PENDING', 'PROCESSING'] and order.service_id.cancel_enabled,
                    'can_refill': order.status == 'COMPLETED' and order.service_id.refill_enabled
                }
            }
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}


    @staticmethod
    def get_order_status_counts(user):
        status_counts = Order.objects.filter(user_id=user).values('status').annotate(
            count=Count('id')
        )
        
        status_dict = {status['status']: status['count'] for status in status_counts}
        
        return {
            'success': True,
            'counts': {
                'pending': status_dict.get('PENDING', 0),
                'processing': status_dict.get('PROCESSING', 0),
                'in_progress': status_dict.get('IN_PROGRESS', 0),
                'completed': status_dict.get('COMPLETED', 0),
                'partial': status_dict.get('PARTIAL', 0),
                'cancelled': status_dict.get('CANCELLED', 0),
                'refunded': status_dict.get('REFUNDED', 0),
                'failed': status_dict.get('FAILED', 0),
                'total': sum(status_dict.values())
            }
        }


    @staticmethod
    def get_recent_orders_user(user, limit=5):
        orders = Order.objects.filter(user_id=user).select_related(
            'service_id'
        ).order_by('-submitted_at')[:limit]
        
        return {
            'success': True,
            'orders': [
                {
                    'id': order.id,
                    'order_number': order.order_number,
                    'service_name': order.service_id.name,
                    'quantity': order.quantity,
                    'price_paid': float(order.price_paid),
                    'status': order.status,
                    'submitted_at': order.submitted_at.isoformat()
                }
                for order in orders
            ]
        }


    @staticmethod
    def get_order_timeline(user, order_id):
        try:
            order = Order.objects.get(id=order_id, user_id=user)
            
            timeline = []

            timeline.append({
                'event': 'Order Submitted',
                'status': 'PENDING',
                'timestamp': order.submitted_at.isoformat(),
                'description': f'Order placed for {order.quantity} units'
            })
            
            if order.status in ['PROCESSING', 'IN_PROGRESS', 'COMPLETED', 'PARTIAL']:
                timeline.append({
                    'event': 'Processing Started',
                    'status': 'PROCESSING',
                    'timestamp': order.submitted_at.isoformat(), 
                    'description': 'Order sent to supplier'
                })

            if order.status in ['IN_PROGRESS', 'COMPLETED', 'PARTIAL']:
                timeline.append({
                    'event': 'Delivery Started',
                    'status': 'IN_PROGRESS',
                    'timestamp': order.submitted_at.isoformat(), 
                    'description': f'Started from count: {order.start_count}'
                })
            
            if order.completed_at:
                timeline.append({
                    'event': 'Order Completed',
                    'status': 'COMPLETED',
                    'timestamp': order.completed_at.isoformat(),
                    'description': f'Successfully delivered {order.quantity - order.remains} units'
                })
            
            if order.cancelled_at:
                timeline.append({
                    'event': 'Order Cancelled',
                    'status': 'CANCELLED',
                    'timestamp': order.cancelled_at.isoformat(),
                    'description': 'Order was cancelled'
                })

            if order.refunded_at:
                timeline.append({
                    'event': 'Order Refunded',
                    'status': 'REFUNDED',
                    'timestamp': order.refunded_at.isoformat(),
                    'description': f'Refunded: ${order.price_paid}'
                })
            
            return {
                'success': True,
                'timeline': timeline
            }
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}


    @staticmethod
    def cancel_order(user, order_id):
        try:
            order = Order.objects.select_related('service_id').get(
                id=order_id, 
                user_id=user
            )
            
            if order.status not in ['PENDING', 'PROCESSING']:
                return {
                    'success': False, 
                    'message': f'Cannot cancel order with status: {order.status}'
                }
            
            if not order.service_id.cancel_enabled:
                return {
                    'success': False,
                    'message': 'This service does not allow cancellations'
                }
            
            order.status = 'CANCELLED'
            order.cancelled_at = timezone.now()
            order.save(update_fields=['status', 'cancelled_at'])
            
            user.balance = F('balance') + order.price_paid
            user.save(update_fields=['balance'])
            
            from users.models import Transaction
            Transaction.objects.create(
                user_id=user,
                type='REFUND',
                amount=order.price_paid,
                balance_before=user.balance - order.price_paid,
                balance_after=user.balance,
                description=f'Refund for cancelled order {order.order_number}',
                reference_id=order.order_number
            )
            
            return {
                'success': True,
                'message': 'Order cancelled successfully',
                'refund_amount': float(order.price_paid)
            }
            
        except Order.DoesNotExist:
            return {'success': False, 'message': 'Order not found'}


    @staticmethod
    def _estimate_completion(order):
        if order.status == 'COMPLETED':
            return None
        
        if order.status in ['CANCELLED', 'FAILED', 'REFUNDED']:
            return None
        
        avg_time = order.service_id.average_time.lower()

        from datetime import timedelta
        
        if 'minute' in avg_time or 'min' in avg_time:
            hours = 0.5
        elif 'hour' in avg_time:
            import re
            numbers = re.findall(r'\d+', avg_time)
            hours = int(numbers[0]) if numbers else 2
        elif 'day' in avg_time:
            import re
            numbers = re.findall(r'\d+', avg_time)
            hours = (int(numbers[0]) if numbers else 1) * 24
        else:
            hours = 24 
        
        estimated = order.submitted_at + timedelta(hours=hours)
        return estimated.isoformat()


    @staticmethod
    def get_order_statistics_user(user):
        from datetime import timedelta
        
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        
        stats = Order.objects.filter(user_id=user).aggregate(
            total_orders=Count('id'),
            total_spent=Sum('price_paid'),
            completed_orders=Count('id', filter=Q(status='COMPLETED')),
            pending_orders=Count('id', filter=Q(status__in=['PENDING', 'PROCESSING', 'IN_PROGRESS'])),
            last_30_days_orders=Count('id', filter=Q(submitted_at__gte=last_30_days)),
            last_30_days_spent=Sum('price_paid', filter=Q(submitted_at__gte=last_30_days))
        )
        
        most_ordered = Order.objects.filter(user_id=user).values(
            'service_id__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        return {
            'success': True,
            'statistics': {
                'lifetime': {
                    'total_orders': stats['total_orders'] or 0,
                    'total_spent': float(stats['total_spent'] or 0),
                    'completed_orders': stats['completed_orders'] or 0,
                    'success_rate': round((stats['completed_orders'] / stats['total_orders'] * 100), 2) if stats['total_orders'] > 0 else 0
                },
                'last_30_days': {
                    'orders': stats['last_30_days_orders'] or 0,
                    'spent': float(stats['last_30_days_spent'] or 0)
                },
                'active': {
                    'pending_orders': stats['pending_orders'] or 0
                },
                'favorite_service': most_ordered['service_id__name'] if most_ordered else None
            }
        }
        
    @staticmethod
    def _generate_order_number():
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(4).upper()
        return f"ORD-{timestamp-{random_part}}"