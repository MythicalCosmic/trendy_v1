from django.urls import re_path
from users.services.ticket_consumer import (
    TicketChatConsumer,
    TicketQueueConsumer,
    AdminDashboardConsumer
)

websocket_urlpatterns = [
    re_path(r'ws/ticket/(?P<ticket_id>\w+)/$', TicketChatConsumer.as_asgi()),
    re_path(r'ws/queue/$', TicketQueueConsumer.as_asgi()),
    re_path(r'ws/admin/dashboard/$', AdminDashboardConsumer.as_asgi()),
]
