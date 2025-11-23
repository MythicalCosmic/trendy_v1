from django.urls import path
from .views import user_views

app_name = 'admins'

urlpatterns = [
    path('users', user_views.list_users, name='list_users'),
    path('users/<int:user_id>', user_views.get_user, name='get_user'),
    path('users/create', user_views.create_user, name='create_user'),
    path('users/<int:user_id>/update', user_views.update_user, name='update_user'),
    path('users/<int:user_id>/delete', user_views.delete_user, name='delete_user'),
    path('users/<int:user_id>/status', user_views.update_user_status, name='update_user_status'),
    path('users/<int:user_id>/role', user_views.update_user_role, name='update_user_role'),
    path('users/<int:user_id>/toggle-api', user_views.toggle_api_access, name='toggle_api_access'),
    path('stats', user_views.get_stats, name='get_stats'),
]