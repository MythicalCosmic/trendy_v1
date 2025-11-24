from rest_framework_api_key.permissions import HasAPIKey
from rest_framework.request import Request
from rest_framework.exceptions import PermissionDenied

def api_key_required(view_func):
    def wrapper(request, *args, **kwargs):
        drf_request = Request(request)
        permission = HasAPIKey()

        if not permission.has_permission(drf_request, view_func):
            raise PermissionDenied("Invalid or missing API key.")

        return view_func(request, *args, **kwargs)

    return wrapper
