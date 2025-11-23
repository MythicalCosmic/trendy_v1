from django.urls import path
from .views import auth_views

app_name = 'users'

urlpatterns = [
    path('register', auth_views.register, name='register'),
    path('login', auth_views.login, name='login'),
    path('logout', auth_views.logout, name='logout'),
    path('refresh', auth_views.refresh_token, name='refresh_token'),
    path('me', auth_views.me, name='me'),
]