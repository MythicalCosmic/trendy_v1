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
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='services')
    supplier_id = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=40, unique=True)
    photo = models.ImageField(upload_to='photos/', blank=True, null=True)
    slug = models.CharField(max_length=40, unique=True, db_index=True)
    description = models.TextField(null=True, blank=True)  
    supplier_service_id = models.IntegerField()
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
    test = models.CharField(default="asd", null=True, blank=True)
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