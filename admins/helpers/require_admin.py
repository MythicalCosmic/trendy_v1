from users.services.auth_service import AuthService
from users.helpers.response import APIResponse
from users.helpers.request import get_token_from_request


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