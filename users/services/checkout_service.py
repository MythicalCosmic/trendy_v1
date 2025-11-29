from django.db import transaction
from django.utils import timezone
from .cart_service import CartService
from .payment_service import PaymentService
from .order_service import OrderService
from .wallet_service import WalletService


class CheckoutService:
    
    @staticmethod
    @transaction.atomic
    def checkout_with_wallet(user):
        cart_result = CartService.get_cart(user)
        
        if not cart_result['success'] or cart_result['cart']['total_items'] == 0:
            return {'success': False, 'message': 'Cart is empty'}
        
        cart = cart_result['cart']
        
        validate_result = CartService.validate_cart(user)
        if not validate_result.get('valid'):
            return {
                'success': False,
                'message': 'Cart validation failed',
                'errors': validate_result.get('errors', [])
            }
        
        deduct_result = WalletService.deduct_funds(
            user=user,
            amount=cart['total_amount'],
            description='Purchase from cart',
            reference_id=None
        )
        
        if not deduct_result['success']:
            return deduct_result
        
        orders_result = OrderService.create_orders_from_cart(user, None)
        
        if not orders_result['success']:
            WalletService.refund(
                user=user,
                amount=cart['total_amount'],
                description='Order creation failed - refund',
                reference_id=None
            )
            return orders_result
        
        return {
            'success': True,
            'orders': orders_result['orders'],
            'total_orders': orders_result['total_orders'],
            'amount_paid': float(cart['total_amount']),
            'balance_remaining': deduct_result['balance'],
            'payment_method': 'wallet',
            'message': 'Orders created successfully using wallet balance'
        }
    
    @staticmethod
    @transaction.atomic
    def checkout_with_payment(user, gateway_slug, currency='USD', callback_url=None):
        cart_result = CartService.get_cart(user)
        
        if not cart_result['success'] or cart_result['cart']['total_items'] == 0:
            return {'success': False, 'message': 'Cart is empty'}
        
        cart = cart_result['cart']
        
        validate_result = CartService.validate_cart(user)
        if not validate_result.get('valid'):
            return {
                'success': False,
                'message': 'Cart validation failed',
                'errors': validate_result.get('errors', [])
            }
        
        payment_result = PaymentService.create_payment(
            user=user,
            amount=cart['total_amount'],
            gateway_slug=gateway_slug,
            currency=currency,
            callback_url=callback_url
        )
        
        if not payment_result['success']:
            return payment_result
        
        return {
            'success': True,
            'payment': payment_result['payment'],
            'cart_total': cart['total_amount'],
            'payment_method': 'gateway',
            'message': 'Payment created. Complete payment to create orders.'
        }
    
    @staticmethod
    @transaction.atomic
    def complete_checkout_after_payment(user, transaction_id):
        from users.models import Payment
        
        try:
            payment = Payment.objects.get(
                transaction_id=transaction_id,
                user_id=user
            )
            
            if payment.status not in ['COMPLETED', 'CONFIRMING']:
                return {
                    'success': False,
                    'message': f'Payment status is {payment.status}. Cannot create orders yet.'
                }
            
            if payment.status == 'COMPLETED' and not payment.completed_at:
                payment.completed_at = timezone.now()
                payment.save()
            
            orders_result = OrderService.create_orders_from_cart(user, transaction_id)
            
            if not orders_result['success']:
                return orders_result
            
            return {
                'success': True,
                'orders': orders_result['orders'],
                'total_orders': orders_result['total_orders'],
                'payment_method': 'gateway',
                'message': 'Orders created successfully'
            }
            
        except Payment.DoesNotExist:
            return {'success': False, 'message': 'Payment not found'}
    
    @staticmethod
    @transaction.atomic
    def add_funds_checkout(user, amount, gateway_slug, currency='USD', callback_url=None):
        payment_result = PaymentService.create_payment(
            user=user,
            amount=amount,
            gateway_slug=gateway_slug,
            currency=currency,
            callback_url=callback_url
        )
        
        if not payment_result['success']:
            return payment_result
        
        return {
            'success': True,
            'payment': payment_result['payment'],
            'message': 'Payment created. Complete payment to add funds to your wallet.'
        }
    
    @staticmethod
    @transaction.atomic
    def complete_payment_to_wallet(payment_id):
        result = WalletService.process_payment_to_wallet(payment_id)
        
        if result['success']:
            return {
                'success': True,
                'balance': result['balance'],
                'amount_added': result['amount_added'],
                'message': result['message']
            }
        
        return result
    
    @staticmethod
    def get_checkout_summary(user):
        cart_result = CartService.get_cart(user)
        
        if not cart_result['success']:
            return cart_result
        
        cart = cart_result['cart']
        balance = WalletService.get_balance(user)
        gateways_result = PaymentService.get_available_gateways()
        
        has_sufficient_balance = balance['balance'] >= cart['total_amount']
        
        return {
            'success': True,
            'summary': {
                'cart': {
                    'total_amount': cart['total_amount'],
                    'total_items': cart['total_items']
                },
                'wallet': {
                    'balance': balance['balance'],
                    'currency': balance['currency'],
                    'can_pay_with_wallet': has_sufficient_balance,
                    'shortfall': max(0, cart['total_amount'] - balance['balance'])
                },
                'payment_options': {
                    'wallet': has_sufficient_balance,
                    'gateway': True,
                    'available_gateways': gateways_result['gateways']
                }
            }
        }