from django.urls import path
from .views import auth_views, category_views, supplier_views


app_name = 'users'

urlpatterns = [
    path('register', auth_views.register, name='register'),
    path('login', auth_views.login, name='login'),
    path('logout', auth_views.logout, name='logout'),
    path('refresh', auth_views.refresh_token, name='refresh_token'),
    path('me', auth_views.me, name='me'),

    path('categories', category_views.list_categories, name='list_categories'),
    path('categories/<str:slug>', category_views.get_category, name='get_category'),

    path('suppliers', supplier_views.list_suppliers, name='list_suppliers'),
    path('suppliers/<int:supplier_id>', supplier_views.get_supplier, name='get_supplier'),
]