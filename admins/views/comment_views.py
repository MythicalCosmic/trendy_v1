from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.services.service_features_service import ServiceFeaturesService
from users.helpers.response import APIResponse
from users.helpers.request import parse_json_body
from admins.helpers.require_admin import require_admin


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def approve_comment(request, comment_id):
    admin_user = request.user
    
    result = ServiceFeaturesService.approve_comment_admin(admin_user, comment_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def reject_comment(request, comment_id):
    admin_user = request.user
    
    result = ServiceFeaturesService.reject_comment_admin(admin_user, comment_id)
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["POST"])
@require_admin
def add_admin_reply(request, comment_id):
    admin_user = request.user
    data, error = parse_json_body(request)
    if error:
        return error
    
    reply = data.get('reply')
    if not reply:
        return APIResponse.validation_error(
            errors={'reply': 'Reply text is required'},
            message='Missing required fields'
        )
    
    result = ServiceFeaturesService.add_admin_reply(
        admin_user=admin_user,
        comment_id=comment_id,
        reply_text=reply
    )
    
    if result['success']:
        return APIResponse.success(message=result['message'])
    
    return APIResponse.error(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_pending_comments(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    result = ServiceFeaturesService.get_pending_comments_admin(
        page=page,
        per_page=per_page
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@require_admin
def get_reported_comments(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    result = ServiceFeaturesService.get_reported_comments_admin(
        page=page,
        per_page=per_page
    )
    
    return APIResponse.success(data=result)