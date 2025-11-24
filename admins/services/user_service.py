from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password
from users.models import User
from django.core.cache import cache


class UserService:
    CACHE_TILL = 300

    @staticmethod
    def get_all_users(page=1, per_page=20, search=None, role=None, status=None, order_by='-id'):
        cache_key = f'users:all:{page}:{per_page}:{search}:{status}:{order_by}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data
        
        queryset = User.objects.only(
            'id', 'first_name', 'last_name', 'email', 'role', 'status', 
            'phone_number', 'country', 'last_login_at', 'api_enabled'
        )
        
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) | 
                Q(first_name__icontains=search) | 
                Q(last_name__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        if role:
            queryset = queryset.filter(role=role)
        
        if status:
            queryset = queryset.filter(status=status)
        
        queryset = queryset.order_by(order_by)
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        result = {
            'success': True,
            'users': list(page_obj.object_list.values()),
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_users': paginator.count,
                'per_page': per_page,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        }
        cache.set(cache_key, result, UserService.CACHE_TILL)
        return result
    
    @staticmethod
    def get_user_by_id(user_id):
        cache_key = f"user:id:{user_id}"
        cache_data = cache.get(cache_key)

        if cache_data:
            return cache_data
        try:
            user = User.objects.only(
                'id', 'first_name', 'last_name', 'email', 'role', 'status',
                'phone_number', 'country', 'timezone', 'api_enabled', 'api_key',
                'last_login_at', 'last_login_api', 'preferences'
            ).get(id=user_id)
            
            result = {
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': user.role,
                    'status': user.status,
                    'phone_number': user.phone_number,
                    'country': user.country,
                    'timezone': user.timezone,
                    'api_enabled': user.api_enabled,
                    'api_key': user.api_key,
                    'last_login_at': str(user.last_login_at) if user.last_login_at else None,
                    'last_login_api': user.last_login_api,
                    'preferences': user.preferences
                }
            }
            cache.set(cache_key, result, UserService.CACHE_TILL)
            return result
        except User.DoesNotExist:
            return {'success': False, 'message': 'User not found'}
    
    @staticmethod
    def create_user(first_name, last_name, email, password, phone_number, 
                   role='USER', status='ACTIVE', country='RU', timezone='UTC+5'):
        try:
            if User.objects.filter(email=email).exists():
                return {'success': False, 'message': 'Email already exists'}
            
            user = User.objects.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=make_password(password),
                phone_number=phone_number,
                role=role,
                status=status,
                country=country,
                timezone=timezone
            )
            
            return {'success': True, 'user': user, 'message': 'User created successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to create user: {str(e)}'}
    
    @staticmethod
    def update_user(user_id, **kwargs):
        try:
            user = User.objects.get(id=user_id)
            
            if 'email' in kwargs and kwargs['email'] != user.email:
                if User.objects.filter(email=kwargs['email']).exists():
                    return {'success': False, 'message': 'Email already exists'}
            
            if 'password' in kwargs:
                kwargs['password'] = make_password(kwargs['password'])
            
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            user.save()
            
            return {'success': True, 'user': user, 'message': 'User updated successfully'}
        except User.DoesNotExist:
            return {'success': False, 'message': 'User not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update user: {str(e)}'}
    
    @staticmethod
    def delete_user(user_id):
        try:
            user = User.objects.get(id=user_id)
            user.delete()
            return {'success': True, 'message': 'User deleted successfully'}
        except User.DoesNotExist:
            return {'success': False, 'message': 'User not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to delete user: {str(e)}'}
    
    @staticmethod
    def update_user_status(user_id, status):
        try:
            User.objects.filter(id=user_id).update(status=status)
            return {'success': True, 'message': f'User status updated to {status}'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update status: {str(e)}'}
    
    @staticmethod
    def update_user_role(user_id, role):
        try:
            User.objects.filter(id=user_id).update(role=role)
            return {'success': True, 'message': f'User role updated to {role}'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update role: {str(e)}'}
    
    @staticmethod
    def toggle_api_access(user_id):
        try:
            user = User.objects.only('id', 'api_enabled').get(id=user_id)
            new_status = not user.api_enabled
            User.objects.filter(id=user_id).update(api_enabled=new_status)
            return {'success': True, 'api_enabled': new_status, 'message': f'API access {"enabled" if new_status else "disabled"}'}
        except User.DoesNotExist:
            return {'success': False, 'message': 'User not found'}
    
    @staticmethod
    def get_user_stats():
        cache_key = 'users:stats'
        cache_data = cache.get(cache_key)

        if cache_data:
            return cache_data
        
        total_users = User.objects.count()
        active_users = User.objects.filter(status='ACTIVE').count()
        suspended_users = User.objects.filter(status='SUSPENDED').count()
        banned_users = User.objects.filter(status='BANNED').count()
        admin_users = User.objects.filter(role='ADMIN').count()
        reseller_users = User.objects.filter(role='RESELLER').count()
        
        result = {
            'success': True,
            'stats': {
                'total_users': total_users,
                'active_users': active_users,
                'suspended_users': suspended_users,
                'banned_users': banned_users,
                'admin_users': admin_users,
                'reseller_users': reseller_users
            }
        }
        cache.set(cache_key, result, UserService.CACHE_TILL)
        return result