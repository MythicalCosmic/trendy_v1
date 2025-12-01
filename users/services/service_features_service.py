from django.db import transaction, models
from django.db.models import Avg, Count, Q, F
from django.utils import timezone
from django.core.paginator import Paginator
from users.models import (
    ServiceComment, ServiceFavorite, CommentHelpful, 
    CommentReport, Service, Order, User
)


class ServiceFeaturesService:
    @staticmethod
    @transaction.atomic
    def add_comment(user, service_id, rating, comment_text, order_id=None):
        try:
            service = Service.objects.get(id=service_id)
            
            existing_comment = ServiceComment.objects.filter(
                user_id=user,
                service_id=service
            ).first()
            
            if existing_comment:
                return {
                    'success': False,
                    'message': 'You have already commented on this service'
                }
            
            if not 1 <= rating <= 5:
                return {
                    'success': False,
                    'message': 'Rating must be between 1 and 5'
                }
            
            is_verified = Order.objects.filter(
                user_id=user,
                service_id=service,
                status='COMPLETED'
            ).exists()
            
            # Create comment
            comment = ServiceComment.objects.create(
                service_id=service,
                user_id=user,
                order_id_id=order_id if order_id else None,
                rating=rating,
                comment=comment_text,
                status='PENDING', 
                is_verified_purchase=is_verified
            )
            
            return {
                'success': True,
                'message': 'Comment submitted for review',
                'comment_id': comment.id
            }
            
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to add comment: {str(e)}'}
    
    @staticmethod
    def get_service_comments(service_id, page=1, per_page=10, approved_only=True):
        queryset = ServiceComment.objects.filter(
            service_id=service_id
        ).select_related('user_id', 'replied_by')
        
        if approved_only:
            queryset = queryset.filter(status='APPROVED')
        
        queryset = queryset.order_by('-created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        comments = [
            {
                'id': comment.id,
                'user': {
                    'name': f"{comment.user_id.first_name} {comment.user_id.last_name}",
                    'email': comment.user_id.email[:3] + '***@***'  
                },
                'rating': comment.rating,
                'comment': comment.comment,
                'is_verified_purchase': comment.is_verified_purchase,
                'helpful_count': comment.helpful_count,
                'status': comment.status,
                'admin_reply': comment.admin_reply,
                'replied_at': comment.replied_at.isoformat() if comment.replied_at else None,
                'created_at': comment.created_at.isoformat()
            }
            for comment in page_obj.object_list
        ]
        
        return {
            'success': True,
            'comments': comments,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_comments': paginator.count
            }
        }
    
    @staticmethod
    @transaction.atomic
    def update_comment(user, comment_id, rating=None, comment_text=None):
        try:
            comment = ServiceComment.objects.select_related('service_id').get(
                id=comment_id,
                user_id=user
            )
            
            if rating and 1 <= rating <= 5:
                comment.rating = rating
            
            if comment_text:
                comment.comment = comment_text
                comment.status = 'PENDING' 
            
            comment.save()
            
            if comment.status == 'APPROVED':
                ServiceFeaturesService._recalculate_service_rating(comment.service_id)
            
            return {
                'success': True,
                'message': 'Comment updated successfully'
            }
            
        except ServiceComment.DoesNotExist:
            return {'success': False, 'message': 'Comment not found'}
    
    @staticmethod
    @transaction.atomic
    def delete_comment(user, comment_id):
        try:
            comment = ServiceComment.objects.select_related('service_id').get(
                id=comment_id,
                user_id=user
            )
            
            service = comment.service_id
            comment.delete()
            
            if comment.status == 'APPROVED':
                ServiceFeaturesService._recalculate_service_rating(service)
            
            return {
                'success': True,
                'message': 'Comment deleted successfully'
            }
            
        except ServiceComment.DoesNotExist:
            return {'success': False, 'message': 'Comment not found'}
    
    @staticmethod
    @transaction.atomic
    def mark_helpful(user, comment_id):
        try:
            comment = ServiceComment.objects.get(id=comment_id)
            helpful = CommentHelpful.objects.filter(
                comment_id=comment,
                user_id=user
            ).first()
            
            if helpful:
                helpful.delete()
                comment.helpful_count = max(0, comment.helpful_count - 1)
                comment.save(update_fields=['helpful_count'])
                return {
                    'success': True,
                    'message': 'Removed helpful mark'
                }
            else:
                CommentHelpful.objects.create(
                    comment_id=comment,
                    user_id=user
                )
                comment.helpful_count = comment.helpful_count + 1
                comment.save(update_fields=['helpful_count'])
                return {
                    'success': True,
                    'message': 'Marked as helpful'
                }
                
        except ServiceComment.DoesNotExist:
            return {'success': False, 'message': 'Comment not found'}
    
    @staticmethod
    @transaction.atomic
    def report_comment(user, comment_id, reason, details=None):
        try:
            comment = ServiceComment.objects.get(id=comment_id)
            existing_report = CommentReport.objects.filter(
                comment_id=comment,
                reported_by=user
            ).exists()
            
            if existing_report:
                return {
                    'success': False,
                    'message': 'You have already reported this comment'
                }
            
            CommentReport.objects.create(
                comment_id=comment,
                reported_by=user,
                reason=reason,
                details=details
            )
            
            comment.reported_count = comment.reported_count + 1
            comment.save(update_fields=['reported_count'])
            
            comment.refresh_from_db()

            if comment.reported_count >= 3:
                comment.status = 'FLAGGED'
                comment.save(update_fields=['status'])
            
            return {
                'success': True,
                'message': 'Comment reported successfully'
            }
            
        except ServiceComment.DoesNotExist:
            return {'success': False, 'message': 'Comment not found'}
    
    @staticmethod
    @transaction.atomic
    def toggle_favorite(user, service_id):
        try:
            service = Service.objects.get(id=service_id)
            
            favorite = ServiceFavorite.objects.filter(
                user_id=user,
                service_id=service
            ).first()
            
            if favorite:
                favorite.delete()
                
                return {
                    'success': True,
                    'message': 'Removed from favorites',
                    'is_favorite': False
                }
            else:
                ServiceFavorite.objects.create(
                    user_id=user,
                    service_id=service
                )
                
                return {
                    'success': True,
                    'message': 'Added to favorites',
                    'is_favorite': True
                }
                
        except Service.DoesNotExist:
            return {'success': False, 'message': 'Service not found'}
    
    @staticmethod
    def get_user_favorites(user, page=1, per_page=20):
        queryset = ServiceFavorite.objects.filter(
            user_id=user
        ).select_related('service_id__category_id').order_by('-created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        favorites = [
            {
                'id': fav.id,
                'service': {
                    'id': fav.service_id.id,
                    'name': fav.service_id.name,
                    'slug': fav.service_id.slug,
                    'category': fav.service_id.category_id.name,
                    'price_per_100': float(fav.service_id.price_per_100),
                    'photo': fav.service_id.photo.url if fav.service_id.photo else None,
                    'is_featured': fav.service_id.is_featured
                },
                'added_at': fav.created_at.isoformat()
            }
            for fav in page_obj.object_list
        ]
        
        return {
            'success': True,
            'favorites': favorites,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_favorites': paginator.count
            }
        }
    
    @staticmethod
    def check_if_favorite(user, service_id):
        is_favorite = ServiceFavorite.objects.filter(
            user_id=user,
            service_id=service_id
        ).exists()
        
        return {
            'success': True,
            'is_favorite': is_favorite
        }
    
    @staticmethod
    @transaction.atomic
    def approve_comment_admin(admin_user, comment_id):
        try:
            comment = ServiceComment.objects.select_related('service_id').get(id=comment_id)
            
            comment.status = 'APPROVED'
            comment.save(update_fields=['status'])
            
            ServiceFeaturesService._recalculate_service_rating(comment.service_id)
            
            return {
                'success': True,
                'message': 'Comment approved'
            }
            
        except ServiceComment.DoesNotExist:
            return {'success': False, 'message': 'Comment not found'}
    
    @staticmethod
    @transaction.atomic
    def reject_comment_admin(admin_user, comment_id):
        try:
            comment = ServiceComment.objects.get(id=comment_id)
            
            comment.status = 'REJECTED'
            comment.save(update_fields=['status'])
            
            return {
                'success': True,
                'message': 'Comment rejected'
            }
            
        except ServiceComment.DoesNotExist:
            return {'success': False, 'message': 'Comment not found'}
    
    @staticmethod
    @transaction.atomic
    def add_admin_reply(admin_user, comment_id, reply_text):
        try:
            comment = ServiceComment.objects.get(id=comment_id)
            
            comment.admin_reply = reply_text
            comment.replied_by = admin_user
            comment.replied_at = timezone.now()
            comment.save(update_fields=['admin_reply', 'replied_by', 'replied_at'])
            
            return {
                'success': True,
                'message': 'Reply added successfully'
            }
            
        except ServiceComment.DoesNotExist:
            return {'success': False, 'message': 'Comment not found'}
    
    @staticmethod
    def get_pending_comments_admin(page=1, per_page=20):
        queryset = ServiceComment.objects.filter(
            status='PENDING'
        ).select_related('user_id', 'service_id').order_by('-created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        comments = [
            {
                'id': comment.id,
                'service': {
                    'id': comment.service_id.id,
                    'name': comment.service_id.name
                },
                'user': {
                    'id': comment.user_id.id,
                    'email': comment.user_id.email,
                    'name': f"{comment.user_id.first_name} {comment.user_id.last_name}"
                },
                'rating': comment.rating,
                'comment': comment.comment,
                'is_verified_purchase': comment.is_verified_purchase,
                'created_at': comment.created_at.isoformat()
            }
            for comment in page_obj.object_list
        ]
        
        return {
            'success': True,
            'comments': comments,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_pending': paginator.count
            }
        }
    
    @staticmethod
    def get_reported_comments_admin(page=1, per_page=20):
        """Get all reported comments for admin review"""
        queryset = CommentReport.objects.filter(
            resolved=False
        ).select_related(
            'comment_id__user_id',
            'comment_id__service_id',
            'reported_by'
        ).order_by('-created_at')
        
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        
        reports = [
            {
                'id': report.id,
                'comment': {
                    'id': report.comment_id.id,
                    'text': report.comment_id.comment,
                    'rating': report.comment_id.rating,
                    'user': report.comment_id.user_id.email
                },
                'service': {
                    'id': report.comment_id.service_id.id,
                    'name': report.comment_id.service_id.name
                },
                'reason': report.reason,
                'details': report.details,
                'reported_by': report.reported_by.email,
                'created_at': report.created_at.isoformat()
            }
            for report in page_obj.object_list
        ]
        
        return {
            'success': True,
            'reports': reports,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_reports': paginator.count
            }
        }
    
    
    @staticmethod
    def _recalculate_service_rating(service):
        stats = ServiceComment.objects.filter(
            service_id=service,
            status='APPROVED'
        ).aggregate(
            avg_rating=Avg('rating'),
            total_count=Count('id')
        )
        
        # Don't use F() - just set the values directly
        # These fields don't exist yet, so we skip them
        # Service.objects.filter(id=service.id).update(
        #     average_rating=stats['avg_rating'] or 0,
        #     total_ratings=stats['total_count'] or 0,
        #     total_comments=stats['total_count'] or 0
        # )
        
        # For now, just pass - you'll need to add these fields to Service model
        pass