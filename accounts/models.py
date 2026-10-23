from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN    = 'admin',    'Admin'
        STAFF    = 'staff',    'Staff'
        CUSTOMER = 'customer', 'Customer'

    email       = models.EmailField(unique=True)
    username    = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text='Optional. Used for login alongside email.'
    )
    first_name  = models.CharField(max_length=50)
    last_name   = models.CharField(max_length=50)
    role        = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone       = models.CharField(max_length=20, blank=True)
    avatar      = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_admin_or_staff(self):
        return self.role in (self.Role.ADMIN, self.Role.STAFF)