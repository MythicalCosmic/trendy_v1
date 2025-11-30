from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.services.order_service import OrderService
from users.helpers.response import APIResponse
from users.helpers.request import parse_json_body
from admins.helpers.require_admin import require_admin


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def list_orders(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    status = request.GET.get('status')
    user_id = request.GET.get('user_id')
    search = request.GET.get('search')
    order_by = request.GET.get('order_by', '-submitted_at')
    
    result = OrderService.get_all_orders_admin(
        page=page,
        per_page=per_page,
        status=status,
        user_id=user_id,
        search=search,
        order_by=order_by
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_order(request, order_id):
    result = OrderService.get_order_by_id_admin(order_id)
    
    if result['success']:
        return APIResponse.success(data=result['order'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["PATCH"])
@require_admin
def update_order_status(request, order_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    status = data.get('status')
    if not status:
        return APIResponse.validation_error(
            errors={'status': 'status is required'},
            message='Missing status field'
        )
    
    result = OrderService.update_order_status(
        order_id=order_id,
        status=status,
        start_count=data.get('start_count'),
        remains=data.get('remains'),
        admin_note=data.get('admin_note')
    )
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_stats(request):
    result = OrderService.get_admin_order_stats()
    return APIResponse.success(data=result['stats'])