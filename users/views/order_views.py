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

@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_order_history(request):
    user = request.user
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    filters = {}
    if request.GET.get('status'):
        filters['status'] = request.GET.get('status')
    if request.GET.get('service_id'):
        filters['service_id'] = request.GET.get('service_id')
    if request.GET.get('date_from'):
        filters['date_from'] = request.GET.get('date_from')
    if request.GET.get('date_to'):
        filters['date_to'] = request.GET.get('date_to')
    if request.GET.get('search'):
        filters['search'] = request.GET.get('search')
    
    result = OrderService.get_user_order_history(
        user=user,
        page=page,
        per_page=per_page,
        filters=filters if filters else None
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_order_detail(request, order_id):
    user = request.user
    
    result = OrderService.get_order_details(user, order_id)
    
    if result['success']:
        return APIResponse.success(data=result['order'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_order_timeline(request, order_id):
    user = request.user
    
    result = OrderService.get_order_timeline(user, order_id)
    
    if result['success']:
        return APIResponse.success(data=result)
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_status_counts(request):
    user = request.user
    
    result = OrderService.get_order_status_counts(user)
    
    return APIResponse.success(data=result['counts'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_recent_orders(request):
    user = request.user
    limit = int(request.GET.get('limit', 5))
    
    result = OrderService.get_recent_orders_user(user, limit)
    
    return APIResponse.success(data=result['orders'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def cancel_order(request, order_id):
    user = request.user
    
    result = OrderService.cancel_order(user, order_id)
    
    if result['success']:
        return APIResponse.success(
            message=result['message'],
            data={'refund_amount': result.get('refund_amount')}
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_order_statistics(request):
    user = request.user
    
    result = OrderService.get_order_statistics_user(user)
    
    return APIResponse.success(data=result['statistics'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def track_order(request, order_number):
    user = request.user
    
    result = OrderService.get_order_by_number(user, order_number)
    
    if result['success']:
        return APIResponse.success(data=result['order'])
    
    return APIResponse.not_found(message=result['message'])