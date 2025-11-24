from rest_framework_api_key.permissions import HasAPIKey
from rest_framework.request import Request
from rest_framework.exceptions import PermissionDenied
from django.core.cache import cache

def api_key_required(view_func):
    def wrapper(request, *args, **kwargs):
        drf_request = Request(request)
        api_key = drf_request.headers.get("X-Api-Key")

        if not api_key:
            raise PermissionDenied("Missing API key.")

        cache_key = f"api_key_valid:{api_key}"
        is_valid = cache.get(cache_key)

        if is_valid is None:
            permission = HasAPIKey()

            if not permission.has_permission(drf_request, view_func):
                raise PermissionDenied("Invalid API key.")

            cache.set(cache_key, True, timeout=60)  

        return view_func(request, *args, **kwargs)

    return wrapper