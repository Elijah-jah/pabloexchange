from django.db import models

# Create your models here.



# ---------------------------------------------------------------------------
# Site settings (singleton) - the uploaded logo powers the favicon + brand
# ---------------------------------------------------------------------------
class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default="PabloExchange")
    logo = models.ImageField(upload_to="site/", blank=True, null=True, max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return "Site settings"
