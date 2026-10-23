from django.db import models
from django.conf import settings


class Announcement(models.Model):

    class Level(models.TextChoices):
        INFO    = 'info', 'Info (Blue)'
        SUCCESS = 'success', 'Sale (Green)'
        WARNING = 'warning', 'Warning (Yellow)'

    title      = models.CharField(max_length=200)
    body       = models.TextField(blank=True)
    level      = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.INFO
    )
    is_active  = models.BooleanField(
        default=True,
        help_text='Uncheck to take down this announcement.'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title