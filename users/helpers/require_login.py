import jwt
from functools import wraps
from django.http import JsonResponse
from django.conf import settings
from users.models import User, Session

JWT_SECRET = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
JWT_ALGO = "HS256"

def user_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return JsonResponse({"message": "Missing token"}, status=401)

        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        except jwt.ExpiredSignatureError:
            return JsonResponse({"message": "Token expired"}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({"message": "Invalid token"}, status=401)
        user_id = payload.get("user_id")

        try:
            user = User.objects.only("id", "role", "status").get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({"message": "User not found"}, status=404)

        if not Session.objects.filter(user_id=user_id, payload=token[:20]).exists():
            return JsonResponse({"message": "Session expired"}, status=401)

        request.user = user
        return view_func(request, *args, **kwargs)

    return wrapper
