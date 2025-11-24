from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ..services.category_service import CategoryService
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
def list_categories(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    search = request.GET.get('search')
    status = request.GET.get('status')
    order_by = request.GET.get('order_by', 'sort_order')
    
    result = CategoryService.get_all_categories(
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
def get_category(request, category_id):
    result = CategoryService.get_category_by_id(category_id)
    
    if result['success']:
        return APIResponse.success(data=result['category'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def create_category(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    required = ['name', 'description', 'icon', 'sort_order']
    missing = [field for field in required if not data.get(field)]
    
    if missing:
        return APIResponse.validation_error(
            errors={field: f'{field} is required' for field in missing},
            message=f'Missing required fields: {", ".join(missing)}'
        )
    
    result = CategoryService.create_category(
        name=data['name'],
        description=data['description'],
        icon=data['icon'],
        sort_order=data['sort_order'],
        status=data.get('status', 'ACTIVE'),
        meta_title=data.get('meta_title'),
        meta_description=data.get('meta_description'),
        slug=data.get('slug')
    )
    
    if result['success']:
        return APIResponse.created(
            data={'category_id': result['category'].id},
            message=result['message']
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@require_admin
def update_category(request, category_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    result = CategoryService.update_category(category_id, **data)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["DELETE"])
@require_admin
def delete_category(request, category_id):
    result = CategoryService.delete_category(category_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["PATCH"])
@require_admin
def update_category_status(request, category_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    status = data.get('status')
    if not status:
        return APIResponse.validation_error(
            errors={'status': 'status is required'},
            message='Missing status field'
        )
    
    result = CategoryService.update_category_status(category_id, status)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def reorder_categories(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    orders = data.get('orders')
    if not orders:
        return APIResponse.validation_error(
            errors={'orders': 'orders array is required'},
            message='Missing orders field'
        )
    
    result = CategoryService.reorder_categories(orders)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_stats(request):
    result = CategoryService.get_category_stats()
    return APIResponse.success(data=result['stats'])