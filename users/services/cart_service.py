from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from users.models import Cart, CartItem, Service, User


class CartService:
    
    @staticmethod
    def get_or_create_cart(user):
        cart, created = Cart.objects.get_or_create(
            user_id=user,
            status='ACTIVE',
            defaults={
                'total_amount': 0,
                'total_items': 0,
                'ip_address': '0.0.0.0',
                'expires_at': timezone.now() + timedelta(days=7)
            }
        )
        return cart

    @staticmethod
    def get_cart(user):
        try:
            cart = Cart.objects.prefetch_related('items__service_id__category_id').get(
                user_id=user,
                status='ACTIVE'
            )
            
            items = []
            for item in cart.items.all():
                items.append({
                    'id': item.id,
                    'service': {
                        'id': item.service_id.id,
                        'name': item.service_id.name,
                        'slug': item.service_id.slug,
                        'photo': item.service_id.photo.url if item.service_id.photo else None,
                        'category': item.service_id.category_id.name
                    },
                    'link': item.link,
                    'quantity': item.quantity,
                    'price_per_100': float(item.price_per_100),
                    'total_amount': float(item.total_amount),
                    'notes': item.notes
                })
            
            return {
                'success': True,
                'cart': {
                    'id': cart.id,
                    'total_amount': float(cart.total_amount),
                    'total_items': cart.total_items,
                    'items': items,
                    'created_at': cart.created_at.isoformat(),
                    'expires_at': cart.expires_at.isoformat() if cart.expires_at else None
                }
            }
        except Cart.DoesNotExist:
            return {
                'success': True,
                'cart': {
                    'id': None,
                    'total_amount': 0,
                    'total_items': 0,
                    'items': []
                }
            }

    @staticmethod
    @transaction.atomic
    def add_to_cart(user, service_id, link, quantity, notes=None, ip_address='0.0.0.0'):
        try:
            service = Service.objects.get(id=service_id, status='ACTIVE')
            
            if quantity < service.min_quantity:
                return {'success': False, 'message': f'Minimum quantity is {service.min_quantity}'}
            
            if quantity > service.max_quantity:
                return {'success': False, 'message': f'Maximum quantity is {service.max_quantity}'}
            
            cart = CartService.get_or_create_cart(user)
            
            price_per_100 = service.price_per_100
            total_amount = (Decimal(quantity) / 100) * price_per_100
            
            existing_item = CartItem.objects.filter(
                cart_id=cart,
                service_id=service,
                link=link
            ).first()
            
            if existing_item:
                existing_item.quantity += quantity
                existing_item.total_amount = (Decimal(existing_item.quantity) / 100) * price_per_100
                if notes:
                    existing_item.notes = notes
                existing_item.save()
                item = existing_item
            else:
                item = CartItem.objects.create(
                    cart_id=cart,
                    service_id=service,
                    link=link,
                    quantity=quantity,
                    price_per_100=price_per_100,
                    total_amount=total_amount,
                    notes=notes
                )
            
            CartService._recalculate_cart(cart)
            
            return {
                'success': True,
                'message': 'Item added to cart',
                'cart_item_id': item.id,
                'cart_total': float(cart.total_amount)
            }
            
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to add to cart: {str(e)}'}

    @staticmethod
    @transaction.atomic
    def update_cart_item(user, item_id, quantity=None, link=None, notes=None):
        try:
            cart = Cart.objects.get(user_id=user.id, status='ACTIVE')
            item = CartItem.objects.select_related('service_id').get(id=item_id, cart_id=cart)
            
            if quantity is not None:
                if quantity < item.service_id.min_quantity:
                    return {'success': False, 'message': f'Minimum quantity is {item.service_id.min_quantity}'}
                
                if quantity > item.service_id.max_quantity:
                    return {'success': False, 'message': f'Maximum quantity is {item.service_id.max_quantity}'}
                
                item.quantity = quantity
                item.total_amount = (Decimal(quantity) / 100) * item.price_per_100
            
            if link:
                item.link = link
            
            if notes is not None:
                item.notes = notes
            
            item.save()
            CartService._recalculate_cart(cart)
            
            return {
                'success': True,
                'message': 'Cart item updated',
                'cart_total': float(cart.total_amount)
            }
            
        except Cart.DoesNotExist:
            return {'success': False, 'message': 'Cart not found'}
        except CartItem.DoesNotExist:
            return {'success': False, 'message': 'Cart item not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update item: {str(e)}'}

    @staticmethod
    @transaction.atomic
    def remove_from_cart(user, item_id):
        try:
            cart = Cart.objects.get(user_id=user.id, status='ACTIVE')
            item = CartItem.objects.get(id=item_id, cart_id=cart)
            
            item.delete()
            CartService._recalculate_cart(cart)
            
            return {
                'success': True,
                'message': 'Item removed from cart',
                'cart_total': float(cart.total_amount)
            }
            
        except Cart.DoesNotExist:
            return {'success': False, 'message': 'Cart not found'}
        except CartItem.DoesNotExist:
            return {'success': False, 'message': 'Cart item not found'}

    @staticmethod
    @transaction.atomic
    def clear_cart(user):
        try:
            cart = Cart.objects.get(user_id=user.id, status='ACTIVE')
            CartItem.objects.filter(cart_id=cart).delete()
            
            cart.total_amount = 0
            cart.total_items = 0
            cart.save()
            
            return {'success': True, 'message': 'Cart cleared'}
            
        except Cart.DoesNotExist:
            return {'success': True, 'message': 'Cart already empty'}

    @staticmethod
    def validate_cart(user):
        try:
            cart = Cart.objects.prefetch_related('items__service_id').get(
                user_id=user,
                status='ACTIVE'
            )
            
            errors = []
            valid_items = []
            
            for item in cart.items.all():
                service = item.service_id

                if service.status != 'ACTIVE':
                    errors.append(f'{service.name} is no longer available')
                    continue
                
                if item.quantity < service.min_quantity:
                    errors.append(f'{service.name}: minimum quantity is {service.min_quantity}')
                    continue
                
                if item.quantity > service.max_quantity:
                    errors.append(f'{service.name}: maximum quantity is {service.max_quantity}')
                    continue
                
                current_price = (Decimal(item.quantity) / 100) * service.price_per_100
                if abs(current_price - item.total_amount) > Decimal('0.01'):
                    item.price_per_100 = service.price_per_100
                    item.total_amount = current_price
                    item.save()
                    errors.append(f'{service.name}: price updated')
                
                valid_items.append(item.id)
            
            if errors:
                return {
                    'success': False,
                    'valid': False,
                    'errors': errors,
                    'valid_items': valid_items
                }
            
            return {'success': True, 'valid': True, 'message': 'Cart is valid'}
            
        except Cart.DoesNotExist:
            return {'success': False, 'message': 'Cart is empty'}

    @staticmethod
    @transaction.atomic
    def mark_as_converted(user, converted_at=None):
        try:
            cart = Cart.objects.get(user_id=user, status='ACTIVE')
            cart.status = 'CONVERTED'
            cart.converted_at = converted_at or timezone.now()
            cart.save()
            
            return {'success': True, 'message': 'Cart marked as converted'}
        except Cart.DoesNotExist:
            return {'success': False, 'message': 'Cart not found'}

    @staticmethod
    def get_cart_summary(user):
        try:
            cart = Cart.objects.prefetch_related('items__service_id').get(
                user_id=user,
                status='ACTIVE'
            )
            
            services_count = cart.items.count()
            total_quantity = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
            
            return {
                'success': True,
                'summary': {
                    'total_amount': float(cart.total_amount),
                    'total_items': cart.total_items,
                    'total_services': services_count,
                    'total_quantity': total_quantity
                }
            }
        except Cart.DoesNotExist:
            return {
                'success': True,
                'summary': {
                    'total_amount': 0,
                    'total_items': 0,
                    'total_services': 0,
                    'total_quantity': 0
                }
            }

    @staticmethod
    def _recalculate_cart(cart):
        items = CartItem.objects.filter(cart_id=cart)
        
        total_amount = items.aggregate(total=Sum('total_amount'))['total'] or 0
        total_items = items.count()
        
        cart.total_amount = total_amount
        cart.total_items = total_items
        cart.save()