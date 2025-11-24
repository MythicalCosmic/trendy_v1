from django.db.models import Q
from django.core.paginator import Paginator
from users.models import Supplier
from django.core.cache import cache

class SupplierService:
    CACHE_TILL = 300

    @staticmethod
    def get_all_suppliers(page=1, per_page=20, search=None, status=None):
        cache_key = f"suppliers:all:{page}:{per_page}:{search}:{status}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data
        
        queryset = Supplier.objects.all()

        if search:
            queryset = queryset.filter(
                Q(first_name__icontaines=search) | 
                Q(last_name_iconatines=search) |
                Q(description__icontaines=search)
            )

        if status:
            queryset = queryset.filter(status=status)

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        result = {
            'suppliers': list(page_obj.object_list.values()),
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_suppliers': paginator.count,
                'per_page': per_page,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        }
        cache.set(cache_key, result, SupplierService.CACHE_TILL)
        return result
    

    @staticmethod
    def get_active_suppliers():
        cache_key = 'suppliers:active'
        cache_data = cache.get(cache_key)

        if cache_data:
            return cache_data
        
        suppliers = Supplier.objects.filter(status='ACTIVE').values(
            'id', 'first_name', 'last_name', 'api_url', 'api_key', 'api_type', 'currency', 'rate_multipler', 'status', 'min_order_amount', 'max_order_amount', 'last_sync_at', 'sync_enabled', 'description', 'support_url', 'terms_url'
        )
        result = {'success': True, 'suppliers': list(suppliers)}
        cache.set(cache_key, result, SupplierService.CACHE_TILL)
        return result