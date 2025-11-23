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

    preferences = models.JSONField(default=dict)

    last_login_at = models.DateField(auto_now_add=True)
    last_login_api = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Session(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.CharField(max_length=20)
    user_agent = models.CharField(max_length=30, null=True, blank=True, default='Chrome')
    payload = models.CharField(max_length=20, null=True, blank=True)
    last_activity = models.DateField(auto_created=True, auto_now_add=True)


class PasswordResetToken(models.Model):
    email = models.ForeignKey(User, to_field='email', on_delete=models.CASCADE)
    token = models.TextField()
    created_at = models.DateField(auto_created=True, auto_now=True, auto_now_add=True)


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
    api_type = models.CharField(max_length=15, choices=SupplierApiKeyType.choices)
    currency = models.CharField(max_length=20)
    rate_multipler = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=SupplerStatus.choices)
    min_order_amount = models.IntegerField()
    max_order_amount = models.IntegerField()
    last_sync_at = models.DateField(auto_created=True, auto_now=True, auto_now_add=True)
    sync_enabled = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    support_url = models.CharField(max_length=50)
    terms_url = models.CharField(max_length=20, null=True, blank=True)

class Service(models.Model):
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE)
    supplier_id = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    name = models.CharField(max_length=40, unique=True)
    slug = models.CharField(max_length=40, unique=True)
    descriptiom = models.TextField(null=True, blank=True)
    supplier_service_id = models.IntegerField()
    price_per_100 = models.FloatField()
    supplier_price_per_100 = models.FloatField()
    min_quantity = models.IntegerField()
    max_quantity = models.IntegerField()
    average_time = models.DateTimeField(auto_created=True, auto_now=True, auto_now_add=True)
    refill_enabled = models.BooleanField(default=False)
    cancell_enabled = models.BooleanField(default=True)
    sort_order = models.CharField(max_length=20)
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=20)
    meta_description = models.TextField(null=True, blank=True)
    total_orders = models.IntegerField()
    total_completed = models.IntegerField()
    

class Cart(models.Model):
    class CartStatus(models.TextChoices):
        active = "ACTIVE", 'Active'
        abandoned = "ADABNDONED", 'Abandoned'
        converted = "CONVERTED", 'Converted'

    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    session_id = models.ForeignKey(Session, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=CartStatus.choices, default=CartStatus.active)
    total_amount = models.IntegerField()
    total_items = models.IntegerField()
    ip_address = models.CharField(max_length=25)
    user_agent = models.CharField(max_length=20, default='Chrome', null=True, blank=True)
    expires_at = models.DateTimeField(auto_created=True, auto_now=True, auto_now_add=True)
    converted_at = models.DateTimeField(auto_created=True, auto_now=True, auto_now_add=True)

class CartItem(models.Model):
    cart_id = models.ForeignKey(Cart, on_delete=models.CASCADE)
    service_id = models.ForeignKey(Service, on_delete=models.CASCADE)
    link = models.CharField(max_length=64)
    quantity = models.IntegerField()
    price_per_100 = models.FloatField()
    total_amount = models.FloatField()
    notes = models.CharField(max_length=20)

class Order(models.Model):
    class OrderStatus(models.TextChoices):
        pending = "PENDING", 'Pending'
        proccessing = "PROCCESSING", 'Proccessing'
        in_progress = "IN_PROGRESS", 'In_progress'
        completed = "COMPLETED", 'Completed'
        partial = "PARTIAL", 'Partial',
        cancelled = "CANCELLED", 'Cancelled',
        refunded = "REFUNDED", 'Refunded',
        failed = "FAILED", 'Failed'

    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    service_id = models.ForeignKey(Service, on_delete=models.CASCADE)
    order_number = models.IntegerField()
    supplier_order_id = models.IntegerField()
    link = models.CharField(max_length=65)
    quantity = models.IntegerField()
    profit = models.FloatField()
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.pending)
    start_count = models.IntegerField()
    remains = models.IntegerField()
    customer_role = models.CharField(max_length=20)
    admin_note = models.CharField(max_length=20)
    submitted_at = models.DateTimeField(auto_created=True, auto_now=True, auto_now_add=True)
    completed_at = models.DateTimeField(auto_created=True, auto_now=True, auto_now_add=True, null=True, blank=True)
    cancelled_at = models.DateTimeField(auto_created=True, auto_now=True, auto_now_add=True, null=True, blank=True)
    refunded_at = models.DateTimeField(auto_created=True, auto_now=True, auto_now_add=True, null=True, blank=True)


class PaymentGateway(models.Model):
    class PaymentGatewaysType(models.TextChoices):
        crypto = "CRYPTO", 'Crypto',
        card = "CARD", 'Card',
        bank_transfer = "BANK_TRANSFER", 'Bank_Transfer',
        other = "OTHER", 'Other',
    
    class PaymentGatewayFeeType(models.TextChoices):
        percentage = "PERCENTAGE", 'Percentage',
        fixed = "FIXED", 'Fixed'
        both = "BOTH", 'Both'

    class PaymentGatewayStatus(models.TextChoices):
        active = "ACTIVE", 'Active'
        inactive = "INACTIVE", 'Inactive'
        maintenance = "MAINTENANCE", 'Maintenance'

    name = models.CharField(max_length=64, unique=True)
    slug = models.CharField(max_length=64, unique=True)
    type = models.CharField(max_length=20, choices=PaymentGatewaysType.card, default=PaymentGatewaysType.card)
    credentials = models.JSONField()
    min_amount = models.FloatField()
    max_amount = models.FloatField()
    fee_type = models.CharField(max_length=20, choices=PaymentGatewayFeeType.choices, default=PaymentGatewayFeeType.percentage)
    fee_percentage = models.FloatField(null=True, blank=True)
    fee_fixed = models.FloatField(null=True, blank=True)
    icon = models.CharField(max_length=20)
    description = models.TextField(null=True, blank=True)
    sort_order = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=PaymentGatewayStatus.active, default=PaymentGatewayStatus.active)
    is_default = models.BooleanField(default=False)
    supported_currencies = models.CharField(max_length=64)

