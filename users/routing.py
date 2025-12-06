from django.urls import re_path
from users.services import ticket_consumer

websocket_urlpatterns = [
    re_path(r'ws/ticket/(?P<ticket_id>\w+)/$', ticket_consumer.TicketChatConsumer.as_asgi()),
    re_path(r'ws/queue/$', ticket_consumer.TicketQueueConsumer.as_asgi()),
    re_path(r'ws/admin/dashboard/$', ticket_consumer.AdminDashboardConsumer.as_asgi()),
]