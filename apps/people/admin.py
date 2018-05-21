from django.contrib import admin
from reversion.admin import VersionAdmin
from django.contrib.auth.admin import UserAdmin

from .models import Address, ArtaUser, EmergencyContact


class AddressInline(admin.StackedInline):
    model = Address
    can_delete = True
    fk_name = 'user'
    extra = 0


class EmergencyContactInline(admin.StackedInline):
    model = EmergencyContact
    can_delete = True
    max_num = EmergencyContact.MAX_PER_USER
    extra = 0


@admin.register(ArtaUser)
class ArtaUserAdmin(UserAdmin, VersionAdmin):
    inlines = (AddressInline, EmergencyContactInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
