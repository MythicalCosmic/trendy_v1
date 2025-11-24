from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from admins.services.category_service import CategoryService
from ..helpers.response import APIResponse
from ..helpers.api_key_require import api_key_required


@csrf_exempt
@api_key_required
@require_http_methods(["GET"])
def list_categories(request):
    result = CategoryService.get_active_categories()
    return APIResponse.success(data=result['categories'])


@csrf_exempt
@api_key_required
@require_http_methods(["GET"])
def get_category(request, slug):
    result = CategoryService.get_category_by_slug(slug)
    
    if result['success']:
        return APIResponse.success(data=result['category'])
    
    return APIResponse.not_found(message=result['message'])