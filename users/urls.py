from django.urls import path
from .views import auth_views, category_views, supplier_views, service_views,cart_views


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

    path('services', service_views.list_services, name='list_services'),
    path('services/featured', service_views.get_featured_services, name='featured_services'),
    path('services/category/<str:category_slug>', service_views.get_services_by_category, name='services_by_category'),
    path('services/<str:slug>', service_views.get_service, name='get_service'),

    path('cart', cart_views.get_cart, name='get_cart'),
    path('cart/add', cart_views.add_to_cart, name='add_to_cart'),
    path('cart/items/<int:item_id>', cart_views.update_cart_item, name='update_cart_item'),
    path('cart/items/<int:item_id>/remove', cart_views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear', cart_views.clear_cart, name='clear_cart'),
    path('cart/validate', cart_views.validate_cart, name='validate_cart'),
    path('cart/summary', cart_views.get_cart_summary, name='cart_summary'),
]