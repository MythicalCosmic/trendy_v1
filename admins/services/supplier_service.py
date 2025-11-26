from django.db.models import Q
from django.core.paginator import Paginator
from django.core.cache import cache
from users.models import Supplier


class SupplierService:
    CACHE_TTL = 300

    @staticmethod
    def get_all_suppliers(page=1, per_page=20, search=None, status=None, order_by='-id'):
        cache_key = f"suppliers:all:{page}:{per_page}:{search}:{status}:{order_by}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data
        
        queryset = Supplier.objects.all()

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) | 
                Q(last_name__icontains=search) |
                Q(description__icontains=search)
            )

        if status:
            queryset = queryset.filter(status=status)

        queryset = queryset.order_by(order_by)

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        result = {
            'success': True,
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
        cache.set(cache_key, result, SupplierService.CACHE_TTL)
        return result
    

    @staticmethod
    def get_active_suppliers():
        cache_key = 'suppliers:active'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data
        
        suppliers = Supplier.objects.filter(status='ACTIVE').values(
            'id', 'first_name', 'last_name', 'api_type', 'currency', 
            'status', 'min_order_amount', 'max_order_amount', 'description'
        )
        result = {'success': True, 'suppliers': list(suppliers)}
        cache.set(cache_key, result, SupplierService.CACHE_TTL)
        return result
    
    @staticmethod
    def get_supplier_by_id(supplier_id):
        cache_key = f'supplier:id:{supplier_id}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data
        
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            result = {
                'success': True,
                'supplier': {
                    'id': supplier.id,
                    'first_name': supplier.first_name,
                    'last_name': supplier.last_name,
                    'api_url': supplier.api_url,
                    'api_key': supplier.api_key,
                    'api_type': supplier.api_type,
                    'currency': supplier.currency,
                    'rate_multipler': supplier.rate_multipler,
                    'status': supplier.status,
                    'min_order_amount': supplier.min_order_amount,
                    'max_order_amount': supplier.max_order_amount,
                    'last_sync_at': str(supplier.last_sync_at) if supplier.last_sync_at else None,
                    'sync_enabled': supplier.sync_enabled,
                    'description': supplier.description,
                    'support_url': supplier.support_url,
                    'terms_url': supplier.terms_url
                }
            }
            cache.set(cache_key, result, SupplierService.CACHE_TTL)
            return result
        except Supplier.DoesNotExist:
            return {'success': False, 'message': 'Supplier not found'}
        

    @staticmethod
    def create_supplier(first_name, last_name, api_url, api_key, api_type, currency, 
                       rate_multipler, min_order_amount, max_order_amount, 
                       description=None, support_url=None, terms_url=None, 
                       status='ACTIVE', sync_enabled=False):
        try:
            if Supplier.objects.filter(api_url=api_url).exists():
                return {'success': False, 'message': 'Supplier with this API URL already exists'}
        
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
                description=description,
                support_url=support_url,
                terms_url=terms_url,
                status=status,
                sync_enabled=sync_enabled
            )
            SupplierService._clear_cache()
            return {'success': True, 'supplier': supplier, 'message': 'Supplier created successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create supplier: {str(e)}'}

    @staticmethod
    def update_supplier(supplier_id, **kwargs):
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            
            if 'api_url' in kwargs and kwargs['api_url'] != supplier.api_url:
                if Supplier.objects.filter(api_url=kwargs['api_url']).exists():
                    return {'success': False, 'message': 'Supplier with this API URL already exists'}
            
            for key, value in kwargs.items():
                if hasattr(supplier, key):
                    setattr(supplier, key, value)
            
            supplier.save()
            SupplierService._clear_cache()
            
            return {'success': True, 'supplier': supplier, 'message': 'Supplier updated successfully'}
        except Supplier.DoesNotExist:
            return {'success': False, 'message': 'Supplier not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update supplier: {str(e)}'}

    @staticmethod
    def delete_supplier(supplier_id):
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            supplier.delete()
            SupplierService._clear_cache()
            return {'success': True, 'message': 'Supplier deleted successfully'}
        except Supplier.DoesNotExist:
            return {'success': False, 'message': 'Supplier not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to delete supplier: {str(e)}'}

    @staticmethod
    def update_supplier_status(supplier_id, status):
        try:
            Supplier.objects.filter(id=supplier_id).update(status=status)
            SupplierService._clear_cache()
            return {'success': True, 'message': f'Supplier status updated to {status}'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update status: {str(e)}'}

    @staticmethod
    def toggle_sync(supplier_id):
        try:
            supplier = Supplier.objects.only('id', 'sync_enabled').get(id=supplier_id)
            new_status = not supplier.sync_enabled
            Supplier.objects.filter(id=supplier_id).update(sync_enabled=new_status)
            SupplierService._clear_cache()
            return {'success': True, 'sync_enabled': new_status, 'message': f'Sync {"enabled" if new_status else "disabled"}'}
        except Supplier.DoesNotExist:
            return {'success': False, 'message': 'Supplier not found'}

    @staticmethod
    def test_supplier_connection(supplier_id):
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            
            return {
                'success': True,
                'message': 'Connection test successful',
                'supplier_name': f'{supplier.first_name} {supplier.last_name}'
            }
        except Supplier.DoesNotExist:
            return {'success': False, 'message': 'Supplier not found'}

    @staticmethod
    def get_supplier_stats():
        cache_key = 'suppliers:stats'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        total = Supplier.objects.count()
        active = Supplier.objects.filter(status='ACTIVE').count()
        inactive = Supplier.objects.filter(status='INACTIVE').count()
        maintenance = Supplier.objects.filter(status='MAINTENANCE').count()
        
        result = {
            'success': True,
            'stats': {
                'total_suppliers': total,
                'active_suppliers': active,
                'inactive_suppliers': inactive,
                'maintenance_suppliers': maintenance
            }
        }
        
        cache.set(cache_key, result, SupplierService.CACHE_TTL)
        return result

    @staticmethod
    def _clear_cache():
        try:
            cache.delete_pattern('suppliers:*')
            cache.delete_pattern('supplier:*')
        except AttributeError:
            cache.clear()