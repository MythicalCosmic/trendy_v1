from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.services.order_service import OrderService
from users.services.auth_service import AuthService
from users.helpers.response import APIResponse
from users.helpers.api_key_require import api_key_required
from users.helpers.require_login import user_required

@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
@user_required
def get_user_orders(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    status = request.GET.get('status')
    
    result = OrderService.get_user_orders(request.user, page, per_page, status)
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
@user_required
def get_order(request, order_number):
    result = OrderService.get_order_by_number(request.user, order_number)
    
    if result['success']:
        return APIResponse.success(data=result['order'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
@user_required
def get_order_stats(request):
    result = OrderService.get_order_stats(request.user)
    return APIResponse.success(data=result['stats'])