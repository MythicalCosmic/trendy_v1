from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils.text import slugify
from users.models import Category


class CategoryService:
    
    @staticmethod
    def get_all_categories(page=1, per_page=20, search=None, status=None, order_by='sort_order'):
        queryset = Category.objects.all()
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search) |
                Q(slug__icontains=search)
            )
        
        if status:
            queryset = queryset.filter(status=status)
        
        queryset = queryset.order_by(order_by)
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            'success': True,
            'categories': list(page_obj.object_list.values()),
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_categories': paginator.count,
                'per_page': per_page,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        }
    
    @staticmethod
    def get_active_categories():
        categories = Category.objects.filter(status='ACTIVE').order_by('sort_order').values(
            'id', 'name', 'slug', 'description', 'icon', 'sort_order'
        )
        return {'success': True, 'categories': list(categories)}
    
    @staticmethod
    def get_category_by_id(category_id):
        try:
            category = Category.objects.get(id=category_id)
            return {
                'success': True,
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'icon': category.icon,
                    'sort_order': category.sort_order,
                    'status': category.status,
                    'meta_title': category.meta_title,
                    'meta_description': category.meta_description
                }
            }
        except Category.DoesNotExist:
            return {'success': False, 'message': 'Category not found'}
    
    @staticmethod
    def get_category_by_slug(slug):
        try:
            category = Category.objects.get(slug=slug, status='ACTIVE')
            return {
                'success': True,
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'icon': category.icon,
                    'meta_title': category.meta_title,
                    'meta_description': category.meta_description
                }
            }
        except Category.DoesNotExist:
            return {'success': False, 'message': 'Category not found'}
    
    @staticmethod
    def create_category(name, description, icon, sort_order, status='ACTIVE', 
                       meta_title=None, meta_description=None, slug=None):
        try:
            if not slug:
                slug = slugify(name)
            
            if Category.objects.filter(slug=slug).exists():
                return {'success': False, 'message': 'Category with this slug already exists'}
            
            if Category.objects.filter(name=name).exists():
                return {'success': False, 'message': 'Category with this name already exists'}
            
            category = Category.objects.create(
                name=name,
                slug=slug,
                description=description,
                icon=icon,
                sort_order=sort_order,
                status=status,
                meta_title=meta_title or name,
                meta_description=meta_description or description
            )
            
            return {'success': True, 'category': category, 'message': 'Category created successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create category: {str(e)}'}
    
    @staticmethod
    def update_category(category_id, **kwargs):
        try:
            category = Category.objects.get(id=category_id)
            
            if 'name' in kwargs and kwargs['name'] != category.name:
                if Category.objects.filter(name=kwargs['name']).exists():
                    return {'success': False, 'message': 'Category with this name already exists'}
                if 'slug' not in kwargs:
                    kwargs['slug'] = slugify(kwargs['name'])
            
            if 'slug' in kwargs and kwargs['slug'] != category.slug:
                if Category.objects.filter(slug=kwargs['slug']).exists():
                    return {'success': False, 'message': 'Category with this slug already exists'}
            
            for key, value in kwargs.items():
                if hasattr(category, key):
                    setattr(category, key, value)
            
            category.save()
            
            return {'success': True, 'category': category, 'message': 'Category updated successfully'}
        except Category.DoesNotExist:
            return {'success': False, 'message': 'Category not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update category: {str(e)}'}
    
    @staticmethod
    def delete_category(category_id):
        try:
            category = Category.objects.get(id=category_id)
            category.delete()
            return {'success': True, 'message': 'Category deleted successfully'}
        except Category.DoesNotExist:
            return {'success': False, 'message': 'Category not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to delete category: {str(e)}'}
    
    @staticmethod
    def update_category_status(category_id, status):
        try:
            Category.objects.filter(id=category_id).update(status=status)
            return {'success': True, 'message': f'Category status updated to {status}'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update status: {str(e)}'}
    
    @staticmethod
    def reorder_categories(category_orders):
        try:
            for item in category_orders:
                Category.objects.filter(id=item['id']).update(sort_order=item['sort_order'])
            return {'success': True, 'message': 'Categories reordered successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to reorder: {str(e)}'}
    
    @staticmethod
    def get_category_stats():
        total = Category.objects.count()
        active = Category.objects.filter(status='ACTIVE').count()
        inactive = Category.objects.filter(status='INACTIVE').count()
        
        return {
            'success': True,
            'stats': {
                'total_categories': total,
                'active_categories': active,
                'inactive_categories': inactive
            }
        }