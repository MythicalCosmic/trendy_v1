from decimal import Decimal
from django.db import transaction
from django.core.paginator import Paginator
from users.models import User, Transaction, Payment


class WalletService:
    
    @staticmethod
    def get_balance(user):
        return {
            'success': True,
            'balance': float(user.balance),
            'currency': user.currency
        }
    
    @staticmethod
    @transaction.atomic
    def add_funds(user, amount, description, reference_id=None):
        try:
            amount = Decimal(str(amount))
            
            if amount <= 0:
                return {'success': False, 'message': 'Amount must be greater than 0'}
            
            balance_before = user.balance
            user.balance += amount
            user.save()
            
            Transaction.objects.create(
                user_id=user,
                type='DEPOSIT',
                amount=amount,
                balance_before=balance_before,
                balance_after=user.balance,
                description=description,
                reference_id=reference_id
            )
            
            return {
                'success': True,
                'balance': float(user.balance),
                'amount_added': float(amount),
                'message': 'Funds added successfully'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to add funds: {str(e)}'}
    
    @staticmethod
    @transaction.atomic
    def deduct_funds(user, amount, description, reference_id=None):
        try:
            amount = Decimal(str(amount))
            
            if amount <= 0:
                return {'success': False, 'message': 'Amount must be greater than 0'}
            
            if user.balance < amount:
                return {
                    'success': False,
                    'message': f'Insufficient balance. Available: {user.balance}, Required: {amount}'
                }
            
            balance_before = user.balance
            user.balance -= amount
            user.save()
            
            Transaction.objects.create(
                user_id=user,
                type='PURCHASE',
                amount=amount,
                balance_before=balance_before,
                balance_after=user.balance,
                description=description,
                reference_id=reference_id
            )
            
            return {
                'success': True,
                'balance': float(user.balance),
                'amount_deducted': float(amount),
                'message': 'Payment successful'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to deduct funds: {str(e)}'}
    
    @staticmethod
    @transaction.atomic
    def refund(user, amount, description, reference_id=None):
        try:
            amount = Decimal(str(amount))
            
            if amount <= 0:
                return {'success': False, 'message': 'Amount must be greater than 0'}
            
            balance_before = user.balance
            user.balance += amount
            user.save()
            
            Transaction.objects.create(
                user_id=user,
                type='REFUND',
                amount=amount,
                balance_before=balance_before,
                balance_after=user.balance,
                description=description,
                reference_id=reference_id
            )
            
            return {
                'success': True,
                'balance': float(user.balance),
                'amount_refunded': float(amount),
                'message': 'Refund processed successfully'
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to process refund: {str(e)}'}
    
    @staticmethod
    def get_transactions(user, page=1, per_page=20, transaction_type=None):
        queryset = Transaction.objects.filter(user_id=user).order_by('-created_at')
        
        if transaction_type:
            queryset = queryset.filter(type=transaction_type)
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        transactions = [{
            'id': t.id,
            'type': t.type,
            'amount': float(t.amount),
            'balance_before': float(t.balance_before),
            'balance_after': float(t.balance_after),
            'description': t.description,
            'reference_id': t.reference_id,
            'created_at': t.created_at.isoformat()
        } for t in page_obj.object_list]
        
        return {
            'success': True,
            'transactions': transactions,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_transactions': paginator.count
            }
        }
    
    @staticmethod
    def get_wallet_stats(user):
        from django.db.models import Sum, Count
        
        deposits = Transaction.objects.filter(
            user_id=user, 
            type='DEPOSIT'
        ).aggregate(total=Sum('amount'), count=Count('id'))
        
        purchases = Transaction.objects.filter(
            user_id=user, 
            type='PURCHASE'
        ).aggregate(total=Sum('amount'), count=Count('id'))
        
        refunds = Transaction.objects.filter(
            user_id=user, 
            type='REFUND'
        ).aggregate(total=Sum('amount'), count=Count('id'))
        
        return {
            'success': True,
            'stats': {
                'current_balance': float(user.balance),
                'currency': user.currency,
                'total_deposited': float(deposits['total'] or 0),
                'total_spent': float(purchases['total'] or 0),
                'total_refunded': float(refunds['total'] or 0),
                'deposit_count': deposits['count'],
                'purchase_count': purchases['count'],
                'refund_count': refunds['count']
            }
        }
    
    @staticmethod
    @transaction.atomic
    def process_payment_to_wallet(payment_id):
        try:
            payment = Payment.objects.select_related('user_id').get(
                payment_id=payment_id,
                status='COMPLETED',
                is_processed=False
            )
            
            result = WalletService.add_funds(
                user=payment.user_id,
                amount=payment.amount,
                description=f'Deposit via {payment.gateway.name if payment.gateway else "payment"}',
                reference_id=payment.transaction_id
            )
            
            if result['success']:
                payment.is_processed = True
                payment.save()
            
            return result
            
        except Payment.DoesNotExist:
            return {'success': False, 'message': 'Payment not found or already processed'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to process payment: {str(e)}'}