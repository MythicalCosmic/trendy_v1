from django.db.models import Q, F, Count, Avg
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils.text import slugify
from django.db import transaction
from users.models import Service, Category, Supplier

class ServiceService:
    CACHE_TTL = 300

    @staticmethod
    def get_all_services(page=1, per_page=20, search=None, category_id=None, 
                        supplier_id=None, status='ACTIVE', is_featured=None, 
                        order_by='sort_order'):
        cache_key = f"services:all:{page}:{per_page}:{search}:{category_id}:{supplier_id}:{status}:{is_featured}:{order_by}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data
        
        queryset = Service.objects.select_related('category_id', 'supplier_id').filter(status=status)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search) |
                Q(slug__icontains=search)
            )

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        if is_featured is not None:
            queryset = queryset.filter(is_featured=is_featured)

        queryset = queryset.order_by(order_by)

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        services = []
        for service in page_obj.object_list:
            services.append({
                'id': service.id,
                'name': service.name,
                'slug': service.slug,
                'photo': service.photo.url if service.photo else None,
                'description': service.description,
                'price_per_100': float(service.price_per_100),
                'min_quantity': service.min_quantity,
                'max_quantity': service.max_quantity,
                'average_time': service.average_time,
                'is_featured': service.is_featured,
                'refill_enabled': service.refill_enabled,
                'cancel_enabled': service.cancel_enabled,
                'category': {
                    'id': service.category_id.id,
                    'name': service.category_id.name,
                    'slug': service.category_id.slug
                },
                'supplier': {
                    'id': service.supplier_id.id,
                    'name': f"{service.supplier_id.first_name} {service.supplier_id.last_name}"
                },
                'total_orders': service.total_orders,
                'total_completed': service.total_completed
            })

        result = {
            'services': services,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_services': paginator.count,
                'per_page': per_page,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        }
        
        cache.set(cache_key, result, ServiceService.CACHE_TTL)
        return result

    @staticmethod
    def get_featured_services(limit=10):
        cache_key = f'services:featured:{limit}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        services = Service.objects.select_related('category_id').filter(
            status='ACTIVE', 
            is_featured=True
        ).order_by('sort_order')[:limit]

        result = {
            'services': [{
                'id': s.id,
                'name': s.name,
                'slug': s.slug,
                'photo': s.photo.url if s.photo else None,
                'price_per_100': float(s.price_per_100),
                'category_name': s.category_id.name,
                'average_time': s.average_time
            } for s in services]
        }

        cache.set(cache_key, result, ServiceService.CACHE_TTL)
        return result

    @staticmethod
    def get_services_by_category(category_slug, page, per_page, request):
        cache_key = f'services:category:{category_slug}:{page}:{per_page}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        try:
            category = Category.objects.get(slug=category_slug, status='ACTIVE')
        except Category.DoesNotExist:
            return {'success': False, 'message': 'Category not found'}

        queryset = Service.objects.select_related('supplier_id').filter(
            category_id=category,
            status='ACTIVE'
        ).order_by('sort_order', 'name')

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        services = [{
            'id': s.id,
            'name': s.name,
            'slug': s.slug,
            "photo": request.build_absolute_uri(s.photo.url),
            'description': s.description,
            'price_per_100': float(s.price_per_100),
            'min_quantity': s.min_quantity,
            'max_quantity': s.max_quantity,
            'average_time': s.average_time,
            'refill_enabled': s.refill_enabled,
            'cancel_enabled': s.cancel_enabled
        } for s in page_obj.object_list]

        result = {
            'success': True,
            'category': {'id': category.id, 'name': category.name, 'slug': category.slug},
            'services': services,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_services': paginator.count
            }
        }

        cache.set(cache_key, result, ServiceService.CACHE_TTL)
        return result

    @staticmethod
    def get_service_by_id(service_id):
        cache_key = f'service:id:{service_id}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        try:
            service = Service.objects.select_related('category_id', 'supplier_id').get(id=service_id)
            result = {
                'success': True,
                'service': ServiceService._serialize_service(service, full=True)
            }
            cache.set(cache_key, result, ServiceService.CACHE_TTL)
            return result
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}

    @staticmethod
    def get_service_by_slug(slug):
        cache_key = f'service:slug:{slug}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        try:
            service = Service.objects.select_related('category_id', 'supplier_id').get(slug=slug, status='ACTIVE')
            result = {
                'success': True,
                'service': ServiceService._serialize_service(service, full=False)
            }
            cache.set(cache_key, result, ServiceService.CACHE_TTL)
            return result
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}

    @staticmethod
    @transaction.atomic
    def create_service(name, category_id, supplier_id, price_per_100, supplier_price_per_100,
                      min_quantity, max_quantity, supplier_service_id, description=None,
                      photo=None, slug=None, average_time='1-2 hours', refill_enabled=False,
                      cancel_enabled=True, sort_order=0, is_featured=False, status='ACTIVE',
                      meta_title=None, meta_description=None):
        try:
            if not slug:
                slug = slugify(name)

            if Service.objects.filter(slug=slug).exists():
                return {'success': False, 'message': 'Service with this slug already exists'}

            if Service.objects.filter(name=name).exists():
                return {'success': False, 'message': 'Service with this name already exists'}

            service = Service.objects.create(
                name=name,
                category_id_id=category_id,
                supplier_id_id=supplier_id,
                slug=slug,
                photo=photo,
                description=description,
                supplier_service_id=supplier_service_id,
                price_per_100=price_per_100,
                supplier_price_per_100=supplier_price_per_100,
                min_quantity=min_quantity,
                max_quantity=max_quantity,
                average_time=average_time,
                refill_enabled=refill_enabled,
                cancel_enabled=cancel_enabled,
                sort_order=sort_order,
                is_featured=is_featured,
                status=status,
                meta_title=meta_title or name,
                meta_description=meta_description or description,
                total_orders=0,
                total_completed=0
            )

            ServiceService._clear_cache()
            return {'success': True, 'service': service, 'message': 'Service created successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create service: {str(e)}'}

    @staticmethod
    @transaction.atomic
    def update_service(service_id, **kwargs):
        try:
            service = Service.objects.get(id=service_id)

            if 'name' in kwargs and kwargs['name'] != service.name:
                if Service.objects.filter(name=kwargs['name']).exists():
                    return {'success': False, 'message': 'Service with this name already exists'}
                if 'slug' not in kwargs:
                    kwargs['slug'] = slugify(kwargs['name'])

            if 'slug' in kwargs and kwargs['slug'] != service.slug:
                if Service.objects.filter(slug=kwargs['slug']).exists():
                    return {'success': False, 'message': 'Service with this slug already exists'}

            for key, value in kwargs.items():
                if hasattr(service, key):
                    setattr(service, key, value)

            service.save()
            ServiceService._clear_cache()

            return {'success': True, 'service': service, 'message': 'Service updated successfully'}
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update service: {str(e)}'}

    @staticmethod
    def delete_service(service_id):
        try:
            service = Service.objects.get(id=service_id)
            service.delete()
            ServiceService._clear_cache()
            return {'success': True, 'message': 'Service deleted successfully'}
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}

    @staticmethod
    def update_service_status(service_id, status):
        try:
            Service.objects.filter(id=service_id).update(status=status)
            ServiceService._clear_cache()
            return {'success': True, 'message': f'Service status updated to {status}'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update status: {str(e)}'}

    @staticmethod
    def toggle_featured(service_id):
        try:
            service = Service.objects.only('id', 'is_featured').get(id=service_id)
            new_status = not service.is_featured
            Service.objects.filter(id=service_id).update(is_featured=new_status)
            ServiceService._clear_cache()
            return {'success': True, 'is_featured': new_status}
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}

    @staticmethod
    def get_service_stats():
        cache_key = 'services:stats'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        total = Service.objects.count()
        active = Service.objects.filter(status='ACTIVE').count()
        inactive = Service.objects.filter(status='INACTIVE').count()
        featured = Service.objects.filter(is_featured=True, status='ACTIVE').count()
        total_orders = Service.objects.aggregate(total=Count('total_orders'))['total'] or 0

        result = {
            'success': True,
            'stats': {
                'total_services': total,
                'active_services': active,
                'inactive_services': inactive,
                'featured_services': featured,
                'total_orders': total_orders
            }
        }

        cache.set(cache_key, result, ServiceService.CACHE_TTL)
        return result

    @staticmethod
    def _serialize_service(service, full=True):
        data = {
            'id': service.id,
            'name': service.name,
            'slug': service.slug,
            'photo': service.photo.url if service.photo else None,
            'description': service.description,
            'price_per_100': float(service.price_per_100),
            'min_quantity': service.min_quantity,
            'max_quantity': service.max_quantity,
            'average_time': service.average_time,
            'refill_enabled': service.refill_enabled,
            'cancel_enabled': service.cancel_enabled,
            'is_featured': service.is_featured,
            'category': {
                'id': service.category_id.id,
                'name': service.category_id.name,
                'slug': service.category_id.slug
            }
        }

        if full:
            data.update({
                'supplier_price_per_100': float(service.supplier_price_per_100),
                'supplier_service_id': service.supplier_service_id,
                'sort_order': service.sort_order,
                'status': service.status,
                'meta_title': service.meta_title,
                'meta_description': service.meta_description,
                'total_orders': service.total_orders,
                'total_completed': service.total_completed,
                'supplier': {
                    'id': service.supplier_id.id,
                    'name': f"{service.supplier_id.first_name} {service.supplier_id.last_name}"
                }
            })

        return data

    @staticmethod
    def _clear_cache():
        try:
            cache.delete_pattern('services:*')
            cache.delete_pattern('service:*')
        except AttributeError:
            cache.clear()