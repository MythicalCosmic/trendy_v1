from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.services.service_features_service import ServiceFeaturesService
from users.helpers.response import APIResponse
from users.helpers.request import parse_json_body
from users.helpers.require_login import user_required


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def add_comment(request, service_id):
    user = request.user
    data, error = parse_json_body(request)
    if error:
        return error
    
    rating = data.get('rating')
    comment = data.get('comment')
    order_id = data.get('order_id')
    
    if not rating or not comment:
        return APIResponse.validation_error(
            errors={'rating': 'Rating and comment are required'},
            message='Missing required fields'
        )
    
    result = ServiceFeaturesService.add_comment(
        user=user,
        service_id=service_id,
        rating=rating,
        comment_text=comment,
        order_id=order_id
    )
    
    if result['success']:
        return APIResponse.success(message=result['message'], data={'comment_id': result.get('comment_id')})
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
def get_service_comments(request, service_id):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))
    
    result = ServiceFeaturesService.get_service_comments(
        service_id=service_id,
        page=page,
        per_page=per_page,
        approved_only=True
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["PATCH"])
@user_required
def update_comment(request, comment_id):
    user = request.user
    data, error = parse_json_body(request)
    if error:
        return error
    
    result = ServiceFeaturesService.update_comment(
        user=user,
        comment_id=comment_id,
        rating=data.get('rating'),
        comment_text=data.get('comment')
    )
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["DELETE"])
@user_required
def delete_comment(request, comment_id):
    user = request.user
    
    result = ServiceFeaturesService.delete_comment(user, comment_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def mark_comment_helpful(request, comment_id):
    user = request.user
    
    result = ServiceFeaturesService.mark_helpful(user, comment_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def report_comment(request, comment_id):
    user = request.user
    data, error = parse_json_body(request)
    if error:
        return error
    
    reason = data.get('reason')
    details = data.get('details')
    
    if not reason:
        return APIResponse.validation_error(
            errors={'reason': 'Reason is required'},
            message='Missing required fields'
        )
    
    result = ServiceFeaturesService.report_comment(
        user=user,
        comment_id=comment_id,
        reason=reason,
        details=details
    )
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@user_required
def toggle_favorite(request, service_id):
    user = request.user
    
    result = ServiceFeaturesService.toggle_favorite(user, service_id)
    
    if result['success']:
        return APIResponse.success(
            message=result['message'],
            data={'is_favorite': result['is_favorite']}
        )
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def get_favorites(request):
    user = request.user
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    result = ServiceFeaturesService.get_user_favorites(
        user=user,
        page=page,
        per_page=per_page
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@user_required
def check_favorite(request, service_id):
    user = request.user
    
    result = ServiceFeaturesService.check_if_favorite(user, service_id)
    
    return APIResponse.success(data=result)