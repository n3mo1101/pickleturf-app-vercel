from django.db import models


class Court(models.Model):
    name        = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Court'

    def __str__(self):
        return self.name