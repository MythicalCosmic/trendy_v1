from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.services.checkout_service import CheckoutService
from users.services.payment_service import PaymentService
from users.services.order_service import OrderService
from users.services.auth_service import AuthService
from users.helpers.response import APIResponse
from users.helpers.request import parse_json_body
from users.helpers.require_login import user_required


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_checkout_summary(request):
    result = CheckoutService.get_checkout_summary(request.user)
    
    if result['success']:
        return APIResponse.success(data=result['summary'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def initiate_checkout(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    payment_method = data.get('payment_method')  
    
    if not payment_method:
        return APIResponse.validation_error(
            errors={'payment_method': 'payment_method is required (wallet or gateway)'},
            message='Missing payment_method'
        )
    
    if payment_method == 'wallet':
        result = CheckoutService.checkout_with_wallet(user=request.user)
    elif payment_method == 'gateway':
        gateway_slug = data.get('gateway_slug')
        if not gateway_slug:
            return APIResponse.validation_error(
                errors={'gateway_slug': 'gateway_slug is required for gateway payment'},
                message='Missing gateway_slug'
            )
        
        result = CheckoutService.checkout_with_payment(
            user=request.user,
            gateway_slug=gateway_slug,
            currency=data.get('currency', 'USD'),
            callback_url=data.get('callback_url')
        )
    else:
        return APIResponse.validation_error(
            errors={'payment_method': 'payment_method must be wallet or gateway'},
            message='Invalid payment_method'
        )
    
    if result['success']:
        return APIResponse.success(data=result, message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def complete_checkout(request, transaction_id):
    result = CheckoutService.complete_checkout_after_payment(request.user, transaction_id)
    
    if result['success']:
        return APIResponse.success(data=result, message=result['message'])
    
    from ..services.payment_service import PaymentService
    payment_result = PaymentService.get_payment_status(transaction_id)
    
    if payment_result['success']:
        payment_status = payment_result['payment']['status']
        if payment_status in ['WAITING', 'CONFIRMING']:
            return APIResponse.error(
                message=f'Payment is still {payment_status}. Please wait for confirmation.',
                data={'status': payment_status}
            )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_payment_gateways(request):
    result = PaymentService.get_available_gateways()
    return APIResponse.success(data=result['gateways'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_payment_status(request, transaction_id):
    result = PaymentService.get_payment_status(transaction_id)
    
    if result['success']:
        return APIResponse.success(data=result['payment'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_user_payments(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    result = PaymentService.get_user_payments(request.user, page, per_page)
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_cryptocurrencies(request):
    result = PaymentService.get_available_cryptocurrencies()
    
    if result['success']:
        return APIResponse.success(data=result['currencies'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
def payment_callback(request, transaction_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    payment_id = data.get('payment_id')
    status = data.get('payment_status')
    
    if not payment_id or not status:
        return APIResponse.error(message='Invalid callback data')
    
    from ..services.payment_service import PaymentService
    from users.models import Payment
    
    result = PaymentService.handle_callback(payment_id, status, data)

    if result['success'] and status in ['finished', 'confirmed']:
        try:
            payment = Payment.objects.get(payment_id=payment_id)
            
            if not payment.is_processed:
                from ..services.cart_service import CartService
                cart_result = CartService.get_cart(payment.user_id)
                
                if cart_result['cart']['total_items'] > 0:
                    CheckoutService.complete_checkout_after_payment(payment.user_id, transaction_id)
                else:
                    CheckoutService.complete_payment_to_wallet(payment_id)
        except Exception as e:
            print(f"Auto-process payment failed: {str(e)}")
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
def payment_success(request):
    transaction_id = request.GET.get('transaction_id')
    
    if not transaction_id:
        return APIResponse.error(message='Transaction ID is required')
    
    try:
        from users.models import Payment
        payment = Payment.objects.get(transaction_id=transaction_id)
        
        from ..services.payment_service import PaymentService
        if payment.gateway and payment.gateway.type == 'CRYPTO' and payment.payment_id:
            PaymentService._sync_nowpayments_status(payment)
            payment.refresh_from_db()
        
        payment_status = payment.status
        
        if payment_status == 'COMPLETED':
            return APIResponse.success(
                data={
                    'transaction_id': transaction_id,
                    'status': payment_status,
                    'message': 'Payment completed! Your orders are being created.',
                    'next_step': f'Call POST /api/checkout/{transaction_id}/complete to create orders'
                }
            )
        elif payment_status in ['WAITING', 'CONFIRMING']:
            return APIResponse.success(
                data={
                    'transaction_id': transaction_id,
                    'status': payment_status,
                    'message': 'Payment is being confirmed. Please wait a moment.',
                    'next_step': f'Check status at GET /api/payment/{transaction_id}'
                }
            )
        else:
            return APIResponse.error(
                message=f'Payment status: {payment_status}',
                data={'transaction_id': transaction_id, 'status': payment_status}
            )
    except Payment.DoesNotExist:
        return APIResponse.not_found(message='Payment not found')
    except Exception as e:
        return APIResponse.error(message=f'Error: {str(e)}')


@csrf_exempt
@require_http_methods(["GET"])
def payment_cancel(request):
    transaction_id = request.GET.get('transaction_id')
    
    return APIResponse.error(
        message='Payment was cancelled',
        data={'transaction_id': transaction_id}
    )