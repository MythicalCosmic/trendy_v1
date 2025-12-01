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
def update_order(request, order_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    result = OrderService.update_order_admin(order_id, **data)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["DELETE"])
@require_admin
def delete_order(request, order_id):
    result = OrderService.delete_order_admin(order_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
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
    
    result = OrderService.update_order_admin(
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
@require_http_methods(["POST"])
@require_admin
def bulk_update_orders(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    order_ids = data.get('order_ids', [])
    if not order_ids:
        return APIResponse.validation_error(
            errors={'order_ids': 'order_ids is required'},
            message='Missing order_ids field'
        )
    
    # Remove order_ids from data before passing as kwargs
    update_data = {k: v for k, v in data.items() if k != 'order_ids'}
    
    result = OrderService.bulk_update_orders_admin(order_ids, **update_data)
    
    if result['success']:
        return APIResponse.success(
            message=result['message'],
            data={'updated_count': result['updated_count']}
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def bulk_delete_orders(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    order_ids = data.get('order_ids', [])
    if not order_ids:
        return APIResponse.validation_error(
            errors={'order_ids': 'order_ids is required'},
            message='Missing order_ids field'
        )
    
    result = OrderService.bulk_delete_orders_admin(order_ids)
    
    if result['success']:
        return APIResponse.success(
            message=result['message'],
            data={'deleted_count': result['deleted_count']}
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_stats(request):
    result = OrderService.get_order_analytics_admin()
    
    if result['success']:
        return APIResponse.success(data=result['analytics'])
    
    return APIResponse.error(message='Failed to fetch stats')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_dashboard_stats(request):
    result = OrderService.get_admin_dashboard_stats()
    
    if result['success']:
        return APIResponse.success(data=result['stats'])
    
    return APIResponse.error(message='Failed to fetch dashboard stats')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_analytics(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    result = OrderService.get_order_analytics_admin(
        start_date=start_date,
        end_date=end_date
    )
    
    if result['success']:
        return APIResponse.success(data=result['analytics'])
    
    return APIResponse.error(message='Failed to fetch analytics')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_revenue_by_period(request):
    period = request.GET.get('period', 'daily')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    result = OrderService.get_revenue_by_period_admin(
        period=period,
        start_date=start_date,
        end_date=end_date
    )
    
    if result['success']:
        return APIResponse.success(data=result)
    
    return APIResponse.error(message='Failed to fetch revenue data')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_top_services(request):
    limit = int(request.GET.get('limit', 10))
    days = int(request.GET.get('days', 30))
    
    result = OrderService.get_top_services_admin(limit=limit, days=days)
    
    if result['success']:
        return APIResponse.success(data=result['services'])
    
    return APIResponse.error(message='Failed to fetch top services')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_top_customers(request):
    limit = int(request.GET.get('limit', 10))
    days = int(request.GET.get('days', 30))
    
    result = OrderService.get_top_customers_admin(limit=limit, days=days)
    
    if result['success']:
        return APIResponse.success(data=result['customers'])
    
    return APIResponse.error(message='Failed to fetch top customers')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_recent_orders(request):
    limit = int(request.GET.get('limit', 10))
    
    result = OrderService.get_recent_orders_admin(limit=limit)
    
    if result['success']:
        return APIResponse.success(data=result['orders'])
    
    return APIResponse.error(message='Failed to fetch recent orders')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_pending_count(request):
    result = OrderService.get_pending_orders_count_admin()
    
    if result['success']:
        return APIResponse.success(data={'pending_count': result['pending_count']})
    
    return APIResponse.error(message='Failed to fetch pending count')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def export_orders(request):
    status = request.GET.get('status')
    user_id = request.GET.get('user_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    result = OrderService.export_orders_admin(
        status=status,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if result['success']:
        return APIResponse.success(data={
            'orders': result['orders'],
            'total_count': result['total_count']
        })
    
    return APIResponse.error(message='Failed to export orders')


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_orders_by_service(request, service_id):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    result = OrderService.get_orders_by_service_admin(
        service_id=service_id,
        page=page,
        per_page=per_page
    )
    
    if result['success']:
        return APIResponse.success(data=result)
    
    return APIResponse.error(message='Failed to fetch orders by service')