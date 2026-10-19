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
    """e.g. under Social: 'Facebook', 'Instagram'."""
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
    """A product line under a subcategory, e.g. 'FB Aged 2012-2015'.
    Carries the shared image + format hint for its items."""
    subcategory = models.ForeignKey(LogSubCategory, on_delete=models.CASCADE,
                                    related_name='groups')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    format_labels = models.CharField(
        max_length=200, blank=True,
        default='UID | PASSWORD | EMAIL PASSWORD | 2FA | RECOVERY EMAIL')
    image = models.ImageField(upload_to='log_groups/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = ('subcategory', 'name')

    def __str__(self):
        return f'{self.subcategory.name} / {self.name}'


class LogItem(models.Model):
    """The sellable listing. stock = number of unsold credentials.
    Decremented automatically on each purchase."""
    group = models.ForeignKey(LogGroup, on_delete=models.CASCADE,
                              related_name='items')
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='log_items/', blank=True, null=True)
    format_labels = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f'{self.title} (₦{self.price}, {self.stock} left)'

    @property
    def display_image(self):
        return self.image or self.group.image

    @property
    def display_format(self):
        return self.format_labels or self.group.format_labels


class LogCredential(models.Model):
    """One line of credentials per unit of stock, e.g.
    'uid:pass | email:pass | 2fa | recovery'. One row = one sale."""
    item = models.ForeignKey(LogItem, on_delete=models.CASCADE,
                             related_name='credentials')
    content = models.TextField(help_text='One credential line, e.g. uid:pass:email:2fa')
    is_sold = models.BooleanField(default=False)
    sold_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'Cred for {self.item.title} ({"sold" if self.is_sold else "in stock"})'


class LogOrder(models.Model):
    """Record of a logs purchase (snapshot keeps history even if item changes)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='log_orders')
    item = models.ForeignKey(LogItem, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='orders')
    item_title = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    credentials = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.item_title} — {self.user} — ₦{self.price}'