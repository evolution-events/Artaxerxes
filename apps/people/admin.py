from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ArtaUser

# Register your models here.

admin.site.register(ArtaUser, UserAdmin)