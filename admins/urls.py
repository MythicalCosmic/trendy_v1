from django.urls import path
from .views import user_views, category_views, supplier_views, service_views, order_views

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

    path('categories', category_views.list_categories, name='list_categories'),
    path('categories/<int:category_id>', category_views.get_category, name='get_category'),
    path('categories/create', category_views.create_category, name='create_category'),
    path('categories/<int:category_id>/update', category_views.update_category, name='update_category'),
    path('categories/<int:category_id>/delete', category_views.delete_category, name='delete_category'),
    path('categories/<int:category_id>/status', category_views.update_category_status, name='update_category_status'),
    path('categories/reorder', category_views.reorder_categories, name='reorder_categories'),
    path('categories/stats', category_views.get_stats, name='get_category_stats'),

    path('suppliers', supplier_views.list_suppliers, name='list_suppliers'),
    path('suppliers/<int:supplier_id>', supplier_views.get_supplier, name='get_supplier'),
    path('suppliers/create', supplier_views.create_supplier, name='create_supplier'),
    path('suppliers/<int:supplier_id>/update', supplier_views.update_supplier, name='update_supplier'),
    path('suppliers/<int:supplier_id>/delete', supplier_views.delete_supplier, name='delete_supplier'),
    path('suppliers/<int:supplier_id>/status', supplier_views.update_supplier_status, name='update_supplier_status'),
    path('suppliers/<int:supplier_id>/toggle-sync', supplier_views.toggle_sync, name='toggle_sync'),
    path('suppliers/<int:supplier_id>/test', supplier_views.test_connection, name='test_connection'),
    path('suppliers/stats', supplier_views.get_stats, name='get_supplier_stats'),

    path('services', service_views.list_services, name='list_services'),
    path('services/<int:service_id>', service_views.get_service, name='get_service'),
    path('services/create', service_views.create_service, name='create_service'),
    path('services/<int:service_id>/update', service_views.update_service, name='update_service'),
    path('services/<int:service_id>/delete', service_views.delete_service, name='delete_service'),
    path('services/<int:service_id>/status', service_views.update_service_status, name='update_service_status'),
    path('services/<int:service_id>/toggle-featured', service_views.toggle_featured, name='toggle_featured'),
    path('services/stats', service_views.get_stats, name='get_service_stats'),

    path('orders', order_views.list_orders, name='list_orders'),
    path('orders/<int:order_id>', order_views.get_order, name='get_order'),
    path('orders/<int:order_id>/status', order_views.update_order_status, name='update_order_status'),
    path('orders/stats', order_views.get_stats, name='get_order_stats'),
]