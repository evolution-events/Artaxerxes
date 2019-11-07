from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _
from reversion.admin import VersionAdmin

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
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('first_name', 'last_name', 'email')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('password',)}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
