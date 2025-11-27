from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from admins.services.service_service import ServiceService
from users.helpers.api_key_require import api_key_required
from users.helpers.response import APIResponse


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
def list_services(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    search = request.GET.get('search')
    category_id = request.GET.get('category_id')
    is_featured = request.GET.get('is_featured')
    
    if is_featured:
        is_featured = is_featured.lower() == 'true'
    
    result = ServiceService.get_all_services(
        page=page,
        per_page=per_page,
        search=search,
        category_id=category_id,
        is_featured=is_featured,
        status='ACTIVE'
    )
    
    return APIResponse.success(data=result)


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
def get_featured_services(request):
    limit = int(request.GET.get('limit', 10))
    result = ServiceService.get_featured_services(limit=limit)
    return APIResponse.success(data=result['services'])


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
def get_services_by_category(request, category_slug):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    
    result = ServiceService.get_services_by_category(category_slug, page, per_page, request)
    
    if result['success']:
        return APIResponse.success(data=result)
    
    return APIResponse.not_found(message=result['message'])


@csrf_exempt
@require_http_methods(["GET"])
@api_key_required
def get_service(request, slug):
    result = ServiceService.get_service_by_slug(slug)
    
    if result['success']:
        return APIResponse.success(data=result['service'])
    
    return APIResponse.not_found(message=result['message'])