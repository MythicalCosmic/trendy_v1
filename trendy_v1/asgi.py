import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trendy_v1.settings')

django_asgi_app = get_asgi_application()

from users.services import ticket_consumer

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter([
                path('ws/ticket/<int:ticket_id>/', ticket_consumer.TicketChatConsumer.as_asgi()),
                path('ws/queue/', ticket_consumer.TicketQueueConsumer.as_asgi()),
                path('ws/admin/dashboard/', ticket_consumer.AdminDashboardConsumer.as_asgi()),
            ])
        )
    ),
})