from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ..services.cart_service import CartService
from users.helpers.response import APIResponse
from users.helpers.request import parse_json_body, get_client_ip
from users.helpers.api_key_require import api_key_required
from users.helpers.require_login import user_required


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
@user_required
def get_cart(request):
    result = CartService.get_cart(request.user.id)
    return APIResponse.success(data=result['cart'])


@csrf_exempt
@require_http_methods(["POST"])
@api_key_required
@user_required
def add_to_cart(request):
    data, error = parse_json_body(request)
    if error:
        return error
    
    required = ['service_id', 'link', 'quantity']
    missing = [field for field in required if field not in data]
    
    if missing:
        return APIResponse.validation_error(
            errors={field: f'{field} is required' for field in missing},
            message=f'Missing required fields: {", ".join(missing)}'
        )
    
    result = CartService.add_to_cart(
        user=request.user,
        service_id=data['service_id'],
        link=data['link'],
        quantity=data['quantity'],
        notes=data.get('notes'),
        ip_address=get_client_ip(request)
    )
    
    if result['success']:
        return APIResponse.success(
            data={
                'cart_item_id': result['cart_item_id'],
                'cart_total': result['cart_total']
            },
            message=result['message']
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@api_key_required
@user_required
def update_cart_item(request, item_id):
    data, error = parse_json_body(request)
    if error:
        return error
    
    result = CartService.update_cart_item(
        user=request.user,
        item_id=item_id,
        quantity=data.get('quantity'),
        link=data.get('link'),
        notes=data.get('notes')
    )
    
    if result['success']:
        return APIResponse.success(
            data={'cart_total': result['cart_total']},
            message=result['message']
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["DELETE"])
@api_key_required
@user_required
def remove_from_cart(request, item_id):
    result = CartService.remove_from_cart(request.user, item_id)
    
    if result['success']:
        return APIResponse.success(
            data={'cart_total': result['cart_total']},
            message=result['message']
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["DELETE"])
@api_key_required
@user_required
def clear_cart(request):
    result = CartService.clear_cart(request.user)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
@user_required
def validate_cart(request):
    result = CartService.validate_cart(request.user)
    
    if result.get('valid'):
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(
        message='Cart validation failed',
        data={'errors': result.get('errors', []), 'valid_items': result.get('valid_items', [])}
    )


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
@user_required
def get_cart_summary(request):
    result = CartService.get_cart_summary(request.user)
    return APIResponse.success(data=result['summary'])