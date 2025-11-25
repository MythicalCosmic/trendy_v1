from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ..services.supplier_service import SupplierService
from users.services.auth_service import AuthService
from users.helpers.response import APIResponse
from users.helpers.request import get_token_from_request, parse_json_body
from datetime import datetime

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

    result = SupplierService.get_all_suppliers(
        page=page,
        per_page=per_page,
        search=search,
        status=status
    )
    return APIResponse.success(data=result)

@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_supplier(request, supplier_id):
    result = SupplierService.get_active_suppliers(supplier_id)

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
    
    required = [
        'first_name', 'last_name', 'api_url', 'api_key', 'api_type',
        'currency', 'rate_multipler', 'min_order_amount',
        'max_order_amount',  
        'description', 'support_url', 'terms_url'
    ]
    
    missing = [field for field in required if not data.get(field)]
    
    if missing:
        return APIResponse.validation_error(
            errors={field: f'{field} is required' for field in missing},
            message=f'Missing required fields: {', '.join(missing)}'
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
        last_sync_at=datetime.now(),
        description=data['description'],
        support_url=data['support_url'],
        terms_url=data['terms_url']
    )

    if result['success']:
        return APIResponse.created(
            data={
                'supplier_id': result['supplier'].id,
                'first_name': result['supplier'].first_name,
                'last_name': result['supplier'].last_name
            }
        )
    
    return APIResponse.error(message=result['message'])