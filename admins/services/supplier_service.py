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
    
    @staticmethod
    def get_supplier_by_id(supplier_id):
        cache_key = f'supplier:id:{supplier_id}'
        cache_data = cache.get(cache_key)

        if cache_data:
            return cache_data
        
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            result = {
                'supplier': {
                    'id': supplier.id,
                    'first_name': supplier.first_name,
                    'last_name': supplier.last_name,
                    'api_url': supplier.api_url,
                    'api_type': supplier.api_type,
                    'currency': supplier.currency,
                    'rate_multiplier': supplier.rate_multipler,
                    'status': supplier.status,
                    'min_order_amount': supplier.min_order_amount,
                    'max_order_amount': supplier.max_order_amount,
                    'last_sync_at': supplier.last_sync_at,
                    'sync_enabled': supplier.sync_enabled,
                    'description': supplier.description,
                    'support_url': supplier.support_url,
                    'terms_url': supplier.terms_url
                }
            }
            cache.set(cache_key, result, SupplierService.CACHE_TILL)
            return result
        
        except Supplier.DoesNotExist:
            return {'success': False, 'message': 'Category not found'}
        

    @staticmethod
    def create_supplier(first_name, last_name, api_url, api_key, api_type, currency, rate_multipler, min_order_amount, max_order_amount, last_sync_at, description, support_url, terms_url, status='ACTIVE', sync_enabled=False):
        try:
            if Supplier.objects.filter(first_name=first_name, last_name=last_name).exists():
                return {'success': False, 'message': 'Supplier wiht these credentials already exists'}
        
            supplier = Supplier.objects.create(
                first_name=first_name,
                last_name=last_name,
                api_url=api_url,
                api_key=api_key,
                api_type=api_type,
                currency=currency,
                rate_multipler=rate_multipler,
                min_order_amount=min_order_amount,
                max_order_amount=max_order_amount,
                last_sync_at=last_sync_at,
                description=description,
                support_url=support_url,
                terms_url=terms_url,
                status=status,
                sync_enabled=sync_enabled
            )
            SupplierService._clear_cache()
            return {'success': True, 'supplier': supplier, 'message': 'Category created successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create supplier: {str(e)}'}


    @staticmethod
    def _clear_cache():
        try:
            cache.delete_pattern('suppliers"*')
            cache.delete_pattern('suppliers:*')
        except AttributeError:
            cache.clear()

