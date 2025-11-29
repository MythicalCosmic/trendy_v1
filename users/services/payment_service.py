import requests
import secrets
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from users.models import Payment, PaymentGateway, User


class PaymentService:
    
    NOWPAYMENTS_API_KEY = "92BPQEY-XZEMXY5-Q6E80ET-J4HSTQ2"
    NOWPAYMENTS_BASE_URL = "https://api.nowpayments.io/v1"
    BASE_URL = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    
    @staticmethod
    def get_available_gateways():
        gateways = PaymentGateway.objects.filter(status='ACTIVE').order_by('sort_order').values(
            'id', 'name', 'slug', 'type', 'icon', 'description', 
            'min_amount', 'max_amount', 'fee_type', 'fee_percentage', 'fee_fixed'
        )
        return {'success': True, 'gateways': list(gateways)}
    
    @staticmethod
    def calculate_fee(amount, gateway):
        amount = Decimal(str(amount))
        fee = Decimal('0')
        
        if gateway.fee_type == 'PERCENTAGE':
            fee = (amount * Decimal(str(gateway.fee_percentage))) / 100
        elif gateway.fee_type == 'FIXED':
            fee = Decimal(str(gateway.fee_fixed))
        elif gateway.fee_type == 'BOTH':
            percentage_fee = (amount * Decimal(str(gateway.fee_percentage))) / 100
            fee = percentage_fee + Decimal(str(gateway.fee_fixed))
        
        return fee
    
    @staticmethod
    @transaction.atomic
    def create_payment(user, amount, gateway_slug, currency='USD', callback_url=None):
        try:
            gateway = PaymentGateway.objects.get(slug=gateway_slug, status='ACTIVE')
            
            amount = Decimal(str(amount))
            
            if amount < gateway.min_amount:
                return {'success': False, 'message': f'Minimum amount is {gateway.min_amount}'}
            
            if amount > gateway.max_amount:
                return {'success': False, 'message': f'Maximum amount is {gateway.max_amount}'}
            
            fee = PaymentService.calculate_fee(amount, gateway)
            total_amount = amount + fee
            
            transaction_id = PaymentService._generate_transaction_id()
            
            payment = Payment.objects.create(
                user_id=user,
                gateway=gateway,
                transaction_id=transaction_id,
                amount=amount,
                fee=fee,
                total_amount=total_amount,
                currency=currency,
                status='PENDING',
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            if gateway.type == 'CRYPTO':
                result = PaymentService._create_nowpayments_invoice(
                    payment, 
                    callback_url or f"{PaymentService.BASE_URL}/api/auth/payment/callback/{transaction_id}"
                )
                if not result['success']:
                    payment.status = 'FAILED'
                    payment.save()
                    return result
                
                payment.payment_id = result['payment_id']
                payment.payment_url = result['payment_url']
                payment.crypto_amount = result.get('crypto_amount')
                payment.crypto_currency = result.get('crypto_currency')
                payment.payment_data = result.get('payment_data', {})
                payment.status = 'WAITING'
                payment.save()
            
            return {
                'success': True,
                'payment': {
                    'transaction_id': payment.transaction_id,
                    'payment_id': payment.payment_id,
                    'amount': float(payment.amount),
                    'fee': float(payment.fee),
                    'total_amount': float(payment.total_amount),
                    'currency': payment.currency,
                    'crypto_currency': payment.crypto_currency,
                    'crypto_amount': float(payment.crypto_amount) if payment.crypto_amount else None,
                    'payment_url': payment.payment_url,
                    'status': payment.status,
                    'expires_at': payment.expires_at.isoformat() if payment.expires_at else None
                },
                'message': 'Payment created successfully'
            }
            
        except PaymentGateway.DoesNotExist:
            return {'success': False, 'message': 'Payment gateway not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create payment: {str(e)}'}
    
    @staticmethod
    def _create_nowpayments_invoice(payment, callback_url):
        try:
            headers = {
                'x-api-key': PaymentService.NOWPAYMENTS_API_KEY,
                'Content-Type': 'application/json'
            }
            
            payload = {
                'price_amount': float(payment.total_amount),
                'price_currency': payment.currency,
                'order_id': payment.transaction_id,
                'order_description': f'Payment for order {payment.transaction_id}',
                'ipn_callback_url': callback_url,
                'success_url': f'{PaymentService.BASE_URL}/api/auth/payment/success?transaction_id={payment.transaction_id}',
                'cancel_url': f'{PaymentService.BASE_URL}/api/auth/payment/cancel?transaction_id={payment.transaction_id}'
            }
            
            response = requests.post(
                f"{PaymentService.NOWPAYMENTS_BASE_URL}/invoice",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                return {
                    'success': True,
                    'payment_id': data.get('id'),
                    'payment_url': data.get('invoice_url'),
                    'crypto_amount': data.get('pay_amount'),
                    'crypto_currency': data.get('pay_currency'),
                    'payment_data': data
                }
            else:
                return {
                    'success': False,
                    'message': f'NOWPayments error: {response.text}'
                }
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'message': f'Connection error: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create invoice: {str(e)}'}
    
    @staticmethod
    def get_payment_status(transaction_id):
        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
            
            if payment.gateway.type == 'CRYPTO' and payment.payment_id:
                PaymentService._sync_nowpayments_status(payment)
            
            return {
                'success': True,
                'payment': {
                    'transaction_id': payment.transaction_id,
                    'amount': float(payment.total_amount),
                    'currency': payment.currency,
                    'status': payment.status,
                    'payment_url': payment.payment_url,
                    'created_at': payment.created_at.isoformat(),
                    'completed_at': payment.completed_at.isoformat() if payment.completed_at else None
                }
            }
        except Payment.DoesNotExist:
            return {'success': False, 'message': 'Payment not found'}
    
    @staticmethod
    def _sync_nowpayments_status(payment):
        try:
            headers = {'x-api-key': PaymentService.NOWPAYMENTS_API_KEY}
            
            response = requests.get(
                f"{PaymentService.NOWPAYMENTS_BASE_URL}/payment/{payment.payment_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status_map = {
                    'waiting': 'WAITING',
                    'confirming': 'CONFIRMING',
                    'confirmed': 'COMPLETED',
                    'sending': 'CONFIRMING',
                    'partially_paid': 'WAITING',
                    'finished': 'COMPLETED',
                    'failed': 'FAILED',
                    'refunded': 'REFUNDED',
                    'expired': 'EXPIRED'
                }
                
                new_status = status_map.get(data.get('payment_status'), 'PENDING')
                
                if new_status != payment.status:
                    payment.status = new_status
                    if new_status == 'COMPLETED':
                        payment.completed_at = timezone.now()
                    payment.payment_data = data
                    payment.save()
                    
        except Exception as e:
            print(f"Failed to sync payment status: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def handle_callback(payment_id, status, payment_data):
        try:
            payment = Payment.objects.get(payment_id=payment_id)
            
            status_map = {
                'finished': 'COMPLETED',
                'confirmed': 'COMPLETED',
                'failed': 'FAILED',
                'expired': 'EXPIRED',
                'refunded': 'REFUNDED'
            }
            
            new_status = status_map.get(status, payment.status)
            
            if new_status != payment.status:
                payment.status = new_status
                payment.payment_data.update(payment_data)
                
                if new_status == 'COMPLETED':
                    payment.completed_at = timezone.now()
                
                payment.save()
            
            return {'success': True, 'message': 'Payment status updated'}
            
        except Payment.DoesNotExist:
            return {'success': False, 'message': 'Payment not found'}
    
    @staticmethod
    def get_user_payments(user, page=1, per_page=20):
        from django.core.paginator import Paginator
        
        queryset = Payment.objects.filter(user_id=user).select_related('gateway').order_by('-created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        payments = [{
            'transaction_id': p.transaction_id,
            'amount': float(p.total_amount),
            'currency': p.currency,
            'gateway': p.gateway.name if p.gateway else 'Unknown',
            'status': p.status,
            'created_at': p.created_at.isoformat()
        } for p in page_obj.object_list]
        
        return {
            'success': True,
            'payments': payments,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_payments': paginator.count
            }
        }
    
    @staticmethod
    def get_available_cryptocurrencies():
        try:
            headers = {'x-api-key': PaymentService.NOWPAYMENTS_API_KEY}
            
            response = requests.get(
                f"{PaymentService.NOWPAYMENTS_BASE_URL}/currencies",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                currencies = response.json().get('currencies', [])
                return {'success': True, 'currencies': currencies}
            
            return {'success': False, 'message': 'Failed to fetch currencies'}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def _generate_transaction_id():
        return f"TXN-{timezone.now().strftime('%Y%m%d')}-{secrets.token_hex(8).upper()}"