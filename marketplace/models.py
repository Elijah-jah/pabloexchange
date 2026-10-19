from django.conf import settings
from django.db import models
from django.utils import timezone


class LogCategory(models.Model):
    """Top level, e.g. 'Social', 'Gaming', 'Email'."""
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Log categories'

    def __str__(self):
        return self.name


class LogSubCategory(models.Model):
    """e.g. under Social: 'Facebook', 'Instagram'.
    Each subcategory becomes a section on the shop page."""
    category = models.ForeignKey(LogCategory, on_delete=models.CASCADE,
                                 related_name='subcategories')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('category', 'name')

    def __str__(self):
        return f'{self.category.name} / {self.name}'


class LogGroup(models.Model):
    """THE PRODUCT CARD. Carries everything the shop shows:
    title (name), price, stock, description, image, format hint."""
    subcategory = models.ForeignKey(LogSubCategory, on_delete=models.CASCADE,
                                    related_name='groups')
    name = models.CharField(max_length=150)              # e.g. 'Facebook Aged 2018 | Email included'
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)       # = unsold LogItem count
    image = models.ImageField(upload_to='log_groups/', blank=True, null=True)
    format_labels = models.CharField(
        max_length=200, blank=True,
        default='UID | PASSWORD | EMAIL PASSWORD | 2FA | RECOVERY EMAIL')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ('subcategory', 'name')

    def __str__(self):
        return f'{self.name} (₦{self.price}, {self.stock} left)'

    @property
    def actual_stock(self):
        return self.items.filter(is_sold=False).count()


class LogItem(models.Model):
    """ONE credential unit of a group — one row = one sale.
    Add rows to restock. Sold rows keep the history."""
    group = models.ForeignKey(LogGroup, on_delete=models.CASCADE,
                              related_name='items')
    content = models.TextField(help_text='One credential line, e.g. uid:pass:email:2fa:recovery')
    is_sold = models.BooleanField(default=False)
    sold_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.group.name} — {"SOLD" if self.is_sold else "in stock"}'


class LogOrder(models.Model):
    """Record of a sale (snapshot survives group edits/deletes)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='log_orders')
    group = models.ForeignKey(LogGroup, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='orders')
    group_name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    credentials = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.group_name} — {self.user} — ₦{self.price}'