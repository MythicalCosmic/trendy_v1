from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from admins.services.supplier_service import SupplierService
from users.services.auth_service import AuthService
from users.helpers.response import APIResponse
from users.helpers.request import get_token_from_request, parse_json_body


def require_admin(view_func):
    def wrapper(request, *args, **kwargs):
        token = get_token_from_request(request)
        if not token:
            return APIResponse.unauthorized(message='Token not provided')
        
        user = AuthService.get_user_from_token(token)
        if not user:
            return APIResponse.unauthorized(message='Invalid or expired token')
        
        if not AuthService.is_admin(user):
            return APIResponse.forbidden(message='Admin access required')
        
        request.user = user
        return view_func(request, *args, **kwargs)
    return wrapper


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def list_suppliers(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    search = request.GET.get('search')
    status = request.GET.get('status')
    order_by = request.GET.get('order_by', '-id')
    
    result = SupplierService.get_all_suppliers(
        page=page,
        per_page=per_page,
        search=search,
        status=status,
        order_by=order_by
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_supplier(request, supplier_id):
    result = SupplierService.get_supplier_by_id(supplier_id)
    
    if result['success']:
        return APIResponse.success(data=result['supplier'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def create_supplier(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    required = ['first_name', 'last_name', 'api_url', 'api_key', 'api_type', 
                'currency', 'rate_multipler', 'min_order_amount', 'max_order_amount']
    missing = [field for field in required if not data.get(field)]
    
    if missing:
        return APIResponse.validation_error(
            errors={field: f'{field} is required' for field in missing},
            message=f'Missing required fields: {", ".join(missing)}'
        )
    
    result = SupplierService.create_supplier(
        first_name=data['first_name'],
        last_name=data['last_name'],
        api_url=data['api_url'],
        api_key=data['api_key'],
        api_type=data['api_type'],
        currency=data['currency'],
        rate_multipler=data['rate_multipler'],
        min_order_amount=data['min_order_amount'],
        max_order_amount=data['max_order_amount'],
        description=data.get('description'),
        support_url=data.get('support_url'),
        terms_url=data.get('terms_url'),
        status=data.get('status', 'ACTIVE'),
        sync_enabled=data.get('sync_enabled', False)
    )
    
    if result['success']:
        return APIResponse.created(
            data={'supplier_id': result['supplier'].id},
            message=result['message']
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@require_admin
def update_supplier(request, supplier_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    result = SupplierService.update_supplier(supplier_id, **data)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["DELETE"])
@require_admin
def delete_supplier(request, supplier_id):
    result = SupplierService.delete_supplier(supplier_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["PATCH"])
@require_admin
def update_supplier_status(request, supplier_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    status = data.get('status')
    if not status:
        return APIResponse.validation_error(
            errors={'status': 'status is required'},
            message='Missing status field'
        )
    
    result = SupplierService.update_supplier_status(supplier_id, status)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def toggle_sync(request, supplier_id):
    result = SupplierService.toggle_sync(supplier_id)
    
    if result['success']:
        return APIResponse.success(
            data={'sync_enabled': result['sync_enabled']},
            message=result['message']
        )
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def test_connection(request, supplier_id):
    result = SupplierService.test_supplier_connection(supplier_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_stats(request):
    result = SupplierService.get_supplier_stats()
    return APIResponse.success(data=result['stats'])