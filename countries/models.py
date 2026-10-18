from django.db import models


class Country(models.Model):
    code = models.CharField(max_length=2, unique=True)      # 'US'
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name