from django.db import models

class User(models.Model):
    class RoleChoices(models.TextChoices):
        USER = "USER", "User"
        ADMIN = "ADMIN", "Admin"
        RESELLER = "RESELLER", "Reseller"

    class UserStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        BANNED = "BANNED", "Banned"

    first_name = models.CharField(max_length=25)
    last_name = models.CharField(max_length=25)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)

    role = models.CharField(
        max_length=10,
        choices=RoleChoices.choices,
        default=RoleChoices.USER
    )

    status = models.CharField(
        max_length=10,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE
    )

    api_key = models.TextField(blank=True)
    api_enabled = models.BooleanField(default=True)
    phone_number = models.CharField(max_length=15)
    country = models.CharField(max_length=20, default='RU')
    timezone = models.CharField(max_length=20, default='UTC+5')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0) 
    currency = models.CharField(max_length=10, default='USD')
    preferences = models.JSONField(default=dict)

    last_login_at = models.DateTimeField(auto_now_add=True)

    last_login_api = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Session(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.CharField(max_length=20)
    user_agent = models.CharField(max_length=30, null=True, blank=True, default='Chrome')
    payload = models.CharField(max_length=20, null=True, blank=True)
    last_activity = models.DateTimeField(auto_now_add=True)



class PasswordResetToken(models.Model):
    email = models.ForeignKey(User, to_field='email', on_delete=models.CASCADE)
    token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, auto_created=True)



class Category(models.Model):
    class CategoryStatus(models.TextChoices):
        active = "ACTIVE", "Active"
        inactive = "INACTIVe", "Inactive"

    name = models.CharField(max_length=25, unique=True)
    slug = models.CharField(max_length=25, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=25)
    sort_order = models.CharField(max_length=20)
    status = models.CharField(max_length=10, choices=CategoryStatus.choices)
    meta_title = models.CharField(max_length=20)
    meta_description = models.TextField()


class Supplier(models.Model):
    class SupplierApiKeyType(models.TextChoices):
        v1 = "V1", 'v1'
        v2 = "V2", 'v2'
        justanotherpanel = 'JUSTANOTHERPANEL', 'justanotherpanel'
    class SupplerStatus(models.TextChoices):
        active = "ACTIVE", 'Active'
        inactive = "INACTIVE", 'inactive'
        maintenance = "MAINTENANCE", 'Maintenance'

    first_name = models.CharField(max_length=25)
    last_name = models.CharField(max_length=25)
    api_url = models.TextField()
    api_key = models.CharField(max_length=64)
    api_type = models.CharField(max_length=20, choices=SupplierApiKeyType.choices)
    currency = models.CharField(max_length=20)
    rate_multipler = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=SupplerStatus.choices)
    min_order_amount = models.IntegerField()
    max_order_amount = models.IntegerField()
    last_sync_at = models.DateTimeField(auto_now_add=True, auto_created=True)
    sync_enabled = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    support_url = models.CharField(max_length=50)
    terms_url = models.CharField(max_length=20, null=True, blank=True)


class Service(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='services')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=40, unique=True)
    photo = models.ImageField(upload_to='photos/', blank=True, null=True)
    slug = models.CharField(max_length=40, unique=True, db_index=True)
    description = models.TextField(null=True, blank=True)  
    supplier_service_id = models.IntegerField()
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text="Average rating from comments"
    )
    total_ratings = models.IntegerField(
        default=0,
        help_text="Total number of ratings"
    )
    total_comments = models.IntegerField(
        default=0,
        help_text="Total approved comments"
    )
    total_favorites = models.IntegerField(
        default=0,
        help_text="Total users who favorited this service"
    )
    price_per_100 = models.DecimalField(max_digits=10, decimal_places=2)  
    supplier_price_per_100 = models.DecimalField(max_digits=10, decimal_places=2)
    min_quantity = models.IntegerField(default=10)
    max_quantity = models.IntegerField(default=100000)
    average_time = models.CharField(max_length=50, default='1-2 hours') 
    refill_enabled = models.BooleanField(default=False)
    cancel_enabled = models.BooleanField(default=True)  
    sort_order = models.IntegerField(default=0, db_index=True)  
    is_featured = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=20, default='ACTIVE')  
    meta_title = models.CharField(max_length=100)
    meta_description = models.TextField(null=True, blank=True)
    total_orders = models.IntegerField(default=0)
    total_completed = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  

    class Meta:
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_featured', 'status']),
            models.Index(fields=['category_id', 'status']),
        ]

class Cart(models.Model):
    class CartStatus(models.TextChoices):
        ACTIVE = "ACTIVE", 'Active'
        ABANDONED = "ABANDONED", 'Abandoned' 
        CONVERTED = "CONVERTED", 'Converted'

    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')
    session_id = models.ForeignKey(Session, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=CartStatus.choices, default=CartStatus.ACTIVE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  
    total_items = models.IntegerField(default=0)
    ip_address = models.CharField(max_length=45) 
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True) 
    converted_at = models.DateTimeField(null=True, blank=True) 

class CartItem(models.Model):
    cart_id = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    service_id = models.ForeignKey(Service, on_delete=models.CASCADE)
    link = models.URLField(max_length=500)  
    quantity = models.IntegerField()
    price_per_100 = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)

class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", 'Pending'
        PROCESSING = "PROCESSING", 'Processing'  
        IN_PROGRESS = "IN_PROGRESS", 'In Progress'
        COMPLETED = "COMPLETED", 'Completed'
        PARTIAL = "PARTIAL", 'Partial'
        CANCELLED = "CANCELLED", 'Cancelled'
        REFUNDED = "REFUNDED", 'Refunded'
        FAILED = "FAILED", 'Failed'

    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    service_id = models.ForeignKey(Service, on_delete=models.CASCADE)
    order_number = models.CharField(max_length=50, unique=True, db_index=True)  
    supplier_order_id = models.CharField(max_length=50, null=True, blank=True)  
    link = models.URLField(max_length=500)
    quantity = models.IntegerField()
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)  
    profit = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    start_count = models.IntegerField(default=0)
    remains = models.IntegerField(default=0)
    customer_note = models.TextField(null=True, blank=True)
    admin_note = models.TextField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['user_id', 'status']),
        ]



class PaymentGateway(models.Model):
    class PaymentGatewaysType(models.TextChoices):
        crypto = "CRYPTO", 'Crypto'
        card = "CARD", 'Card'
        bank_transfer = "BANK_TRANSFER", 'Bank_Transfer'
        other = "OTHER", 'Other'
    
    class PaymentGatewayFeeType(models.TextChoices):
        percentage = "PERCENTAGE", 'Percentage'
        fixed = "FIXED", 'Fixed'
        both = "BOTH", 'Both'

    class PaymentGatewayStatus(models.TextChoices):
        active = "ACTIVE", 'Active'
        inactive = "INACTIVE", 'Inactive'
        maintenance = "MAINTENANCE", 'Maintenance'

    name = models.CharField(max_length=64, unique=True)
    slug = models.CharField(max_length=64, unique=True)
    type = models.CharField(max_length=20, choices=PaymentGatewaysType.choices, default=PaymentGatewaysType.card)
    credentials = models.JSONField()
    min_amount = models.FloatField()
    max_amount = models.FloatField()
    fee_type = models.CharField(max_length=20, choices=PaymentGatewayFeeType.choices, default=PaymentGatewayFeeType.percentage)
    fee_percentage = models.FloatField(null=True, blank=True)
    fee_fixed = models.FloatField(null=True, blank=True)
    icon = models.CharField(max_length=20)
    description = models.TextField(null=True, blank=True)
    sort_order = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=PaymentGatewayStatus.choices, default=PaymentGatewayStatus.active)
    is_default = models.BooleanField(default=False)
    supported_currencies = models.CharField(max_length=64)


class Payment(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", 'Pending'
        WAITING = "WAITING", 'Waiting for Payment'
        CONFIRMING = "CONFIRMING", 'Confirming'
        COMPLETED = "COMPLETED", 'Completed'
        FAILED = "FAILED", 'Failed'
        CANCELLED = "CANCELLED", 'Cancelled'
        REFUNDED = "REFUNDED", 'Refunded'
        EXPIRED = "EXPIRED", 'Expired'
    
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    test = models.CharField(default="test", max_length=255, null=True, blank=True)
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.SET_NULL, null=True)
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    payment_id = models.CharField(max_length=100, null=True, blank=True) 
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    crypto_currency = models.CharField(max_length=20, null=True, blank=True)  
    crypto_amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    payment_url = models.URLField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['payment_id']),
            models.Index(fields=['user_id', 'status']),
        ]

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = "DEPOSIT", 'Deposit'
        PURCHASE = "PURCHASE", 'Purchase'
        REFUND = "REFUND", 'Refund'
        ADMIN_CREDIT = "ADMIN_CREDIT", 'Admin Credit'
        ADMIN_DEBIT = "ADMIN_DEBIT", 'Admin Debit'
    
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    reference_id = models.CharField(max_length=100, null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', 'type']),
        ]

class OrderHistory(models.Model):
    class EventType(models.TextChoices):
        CREATED = "CREATED", "Order Created"
        STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"
        PROGRESS_UPDATE = "PROGRESS_UPDATE", "Progress Updated"
        CANCELLED = "CANCELLED", "Order Cancelled"
        REFUNDED = "REFUNDED", "Order Refunded"
        NOTE_ADDED = "NOTE_ADDED", "Note Added"
        SUPPLIER_SUBMITTED = "SUPPLIER_SUBMITTED", "Submitted to Supplier"
        ADMIN_UPDATE = "ADMIN_UPDATE", "Admin Update"
    
    order_id = models.ForeignKey(
        'Order', 
        on_delete=models.CASCADE, 
        related_name='history'
    )
    event_type = models.CharField(
        max_length=20, 
        choices=EventType.choices
    )
    old_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20, null=True, blank=True)
    old_value = models.JSONField(null=True, blank=True)  
    new_value = models.JSONField(null=True, blank=True)
    description = models.TextField()
    performed_by = models.ForeignKey(
        'User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='order_actions'
    )
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_id', '-created_at']),
            models.Index(fields=['event_type']),
        ]
        verbose_name_plural = "Order Histories"
    
    def __str__(self):
        return f"{self.order_id.order_number} - {self.event_type} at {self.created_at}"


class OrderNote(models.Model):
    class NoteType(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer Note"
        ADMIN = "ADMIN", "Admin Note"
        SYSTEM = "SYSTEM", "System Note"
    
    order_id = models.ForeignKey(
        'Order', 
        on_delete=models.CASCADE, 
        related_name='notes'
    )
    note_type = models.CharField(
        max_length=10, 
        choices=NoteType.choices,
        default=NoteType.CUSTOMER
    )
    content = models.TextField()
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_visible_to_customer = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_id', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.note_type} for {self.order_id.order_number}"


class OrderStatusLog(models.Model):    
    order_id = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='status_logs'
    )
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_id', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.order_id.order_number}: {self.from_status} → {self.to_status}"

class ServiceComment(models.Model):    
    class CommentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        FLAGGED = "FLAGGED", "Flagged"
    
    service_id = models.ForeignKey(
        'Service',
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user_id = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='service_comments'
    )
    order_id = models.ForeignKey(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comments',
        help_text="Optional: Link comment to an order"
    )
    rating = models.IntegerField(
        default=5,
        help_text="Rating from 1 to 5"
    )
    comment = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=CommentStatus.choices,
        default=CommentStatus.PENDING
    )
    is_verified_purchase = models.BooleanField(
        default=False,
        help_text="True if user has completed an order for this service"
    )
    helpful_count = models.IntegerField(default=0)
    reported_count = models.IntegerField(default=0)
    admin_reply = models.TextField(null=True, blank=True)
    replied_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_replies'
    )
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service_id', 'status', '-created_at']),
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['service_id', 'user_id'],
                name='unique_user_service_comment'
            )
        ]
    
    def __str__(self):
        return f"{self.user_id.email} - {self.service_id.name} ({self.rating}★)"


class ServiceFavorite(models.Model):
    
    user_id = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='favorite_services'
    )
    service_id = models.ForeignKey(
        'Service',
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['service_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'service_id'],
                name='unique_user_favorite_service'
            )
        ]
    
    def __str__(self):
        return f"{self.user_id.email} ❤️ {self.service_id.name}"


class CommentHelpful(models.Model):
    
    comment_id = models.ForeignKey(
        'ServiceComment',
        on_delete=models.CASCADE,
        related_name='helpful_votes'
    )
    user_id = models.ForeignKey(
        'User',
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['comment_id', 'user_id'],
                name='unique_helpful_vote'
            )
        ]
    
    def __str__(self):
        return f"{self.user_id.email} found comment helpful"


class CommentReport(models.Model):
    
    class ReportReason(models.TextChoices):
        SPAM = "SPAM", "Spam"
        OFFENSIVE = "OFFENSIVE", "Offensive Language"
        FAKE = "FAKE", "Fake Review"
        INAPPROPRIATE = "INAPPROPRIATE", "Inappropriate Content"
        OTHER = "OTHER", "Other"
    
    comment_id = models.ForeignKey(
        'ServiceComment',
        on_delete=models.CASCADE,
        related_name='reports'
    )
    reported_by = models.ForeignKey(
        'User',
        on_delete=models.CASCADE
    )
    reason = models.CharField(
        max_length=20,
        choices=ReportReason.choices
    )
    details = models.TextField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_reports'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['comment_id', 'resolved']),
        ]


class SupportTicket(models.Model):
    
    class TicketStatus(models.TextChoices):
        OPEN = "OPEN", "Open"
        PENDING = "PENDING", "Pending Customer Response"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        WAITING = "WAITING", "Waiting for Admin"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"
    
    class TicketPriority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"
    
    class TicketCategory(models.TextChoices):
        GENERAL = "GENERAL", "General Inquiry"
        ORDER = "ORDER", "Order Issue"
        PAYMENT = "PAYMENT", "Payment Issue"
        ACCOUNT = "ACCOUNT", "Account Issue"
        TECHNICAL = "TECHNICAL", "Technical Issue"
        REFUND = "REFUND", "Refund Request"
        OTHER = "OTHER", "Other"
    
    user_id = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    ticket_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )
    subject = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20,
        choices=TicketCategory.choices,
        default=TicketCategory.GENERAL
    )
    priority = models.CharField(
        max_length=10,
        choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM
    )
    status = models.CharField(
        max_length=15,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN
    )

    assigned_to = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        help_text="Admin assigned to this ticket"
    )
    queue_position = models.IntegerField(
        default=0,
        help_text="Position in queue (0 = assigned, >0 = waiting)"
    )

    order_id = models.ForeignKey(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    rating = models.IntegerField(
        null=True,
        blank=True,
        help_text="Customer satisfaction rating (1-5)"
    )
    feedback = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket_number']),
            models.Index(fields=['user_id', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['status', 'priority', 'created_at']),
            models.Index(fields=['queue_position', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"


class TicketMessage(models.Model):
    
    class MessageType(models.TextChoices):
        USER = "USER", "User Message"
        ADMIN = "ADMIN", "Admin Reply"
        SYSTEM = "SYSTEM", "System Message"
        NOTE = "NOTE", "Internal Note"
    
    ticket_id = models.ForeignKey(
        'SupportTicket',
        on_delete=models.CASCADE,
        related_name='messages'
    )
    user_id = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.USER
    )
    message = models.TextField()
    is_internal = models.BooleanField(
        default=False,
        help_text="Internal notes not visible to customer"
    )
    
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of attachment URLs"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"Message in {self.ticket_id.ticket_number}"


class TicketAssignment(models.Model):
    
    ticket_id = models.ForeignKey(
        'SupportTicket',
        on_delete=models.CASCADE,
        related_name='assignment_history'
    )
    assigned_from = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_made_from'
    )
    assigned_to = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_received'
    )
    assigned_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_made'
    )
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ticket_id.ticket_number} assigned to {self.assigned_to}"


class TicketStatusHistory(models.Model):
    
    ticket_id = models.ForeignKey(
        'SupportTicket',
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    from_status = models.CharField(max_length=15)
    to_status = models.CharField(max_length=15)
    changed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ticket_id.ticket_number}: {self.from_status} → {self.to_status}"


class TicketTag(models.Model):
    
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text="Hex color code"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class TicketTagRelation(models.Model):
    
    ticket_id = models.ForeignKey(
        'SupportTicket',
        on_delete=models.CASCADE,
        related_name='ticket_tags'
    )
    tag_id = models.ForeignKey(
        'TicketTag',
        on_delete=models.CASCADE
    )
    added_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['ticket_id', 'tag_id']


class AdminAvailability(models.Model):
    
    class AvailabilityStatus(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        AWAY = "AWAY", "Away"
        BUSY = "BUSY", "Busy"
        OFFLINE = "OFFLINE", "Offline"
    
    admin_id = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='availability'
    )
    status = models.CharField(
        max_length=10,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.OFFLINE
    )
    max_tickets = models.IntegerField(
        default=10,
        help_text="Maximum concurrent tickets"
    )
    current_tickets = models.IntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.admin_id.email} - {self.status}"
    
    @property
    def can_accept_tickets(self):
        return (
            self.status == self.AvailabilityStatus.ONLINE and 
            self.current_tickets < self.max_tickets
        )