from django.conf import settings
from django.db import models, transaction


class LogCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class LogSubCategory(models.Model):
    category = models.ForeignKey(LogCategory, on_delete=models.CASCADE,
                                 related_name='subcategories')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f'{self.category.name} — {self.name}'


class LogGroup(models.Model):
    """The product card — 'United States Facebook', etc."""
    subcategory = models.ForeignKey(LogSubCategory, on_delete=models.CASCADE,
                                    related_name='groups')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    format_labels = models.CharField(
        max_length=255,
        default='UID | PASSWORD | EMAIL PASSWORD | 2FA | RECOVERY EMAIL',
        help_text='Pipe-separated format shown on the buy card')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='log_groups/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def actual_stock(self):
        return self.items.filter(is_sold=False).count()


class LogItem(models.Model):
    """One credential line — restock by adding rows in the admin."""
    group = models.ForeignKey(LogGroup, on_delete=models.CASCADE, related_name='items')
    content = models.TextField(
        help_text='One credential line, e.g. uid:pass:email:2fa:recovery')
    is_sold = models.BooleanField(default=False)
    sold_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.group.name} — {self.content[:40]}'


class LogOrderCounter(models.Model):
    """Atomic counter for PLOG order IDs."""
    last_number = models.PositiveIntegerField(default=1000)

    @classmethod
    def get_next(cls):
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save()
            return counter.last_number


class LogOrder(models.Model):
    """Record of a sale (snapshot survives group edits/deletes).

    Flow: waiting (reserved, nothing paid) -> completed (creds delivered,
    wallet debited) | cancelled (free) | expired (never delivered)."""

    STATUS_CHOICES = (
        ('waiting', 'Waiting'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='log_orders')
    group = models.ForeignKey(LogGroup, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='orders')
    item = models.OneToOneField(LogItem, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='order',
                                help_text='The exact cred line delivered — one item can only ever be sold once')
    order_id = models.CharField(max_length=20, unique=True, editable=False,
                                blank=True)
    group_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    credentials = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f'PLOG{LogOrderCounter.get_next()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.order_id} — {self.group_name} — ₦{self.price} [{self.status}]'