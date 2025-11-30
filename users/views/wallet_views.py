from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.services.wallet_service import WalletService
from users.services.checkout_service import CheckoutService
from users.helpers.response import APIResponse
from users.helpers.request import parse_json_body
from users.helpers.require_login import user_required


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_balance(request):
    result = WalletService.get_balance(request.user)
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_transactions(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    transaction_type = request.GET.get('type')
    
    result = WalletService.get_transactions(request.user, page, per_page, transaction_type)
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_wallet_stats(request):
    result = WalletService.get_wallet_stats(request.user)
    return APIResponse.success(data=result['stats'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def initiate_add_funds(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    required = ['amount', 'gateway_slug']
    missing = [field for field in required if field not in data]
    
    if missing:
        return APIResponse.validation_error(
            errors={field: f'{field} is required' for field in missing},
            message=f'Missing required fields: {", ".join(missing)}'
        )
    
    result = CheckoutService.add_funds_checkout(
        user=request.user,
        amount=data['amount'],
        gateway_slug=data['gateway_slug'],
        currency=data.get('currency', 'USD'),
        callback_url=data.get('callback_url')
    )
    
    if result['success']:
        return APIResponse.success(data=result, message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def checkout_with_balance(request):
    result = CheckoutService.checkout_with_wallet(request.user)
    
    if result['success']:
        return APIResponse.success(data=result, message=result['message'])
    
    return APIResponse.error(message=result['message'])