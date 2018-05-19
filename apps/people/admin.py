from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ArtaUser, Address
from django.utils.translation import gettext as _, ngettext, ugettext_lazy


class AddressInline(admin.StackedInline):
    model = Address
    can_delete = True
    fk_name = 'user'


class ArtaUserAdmin(UserAdmin):
    inlines = (AddressInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')


# Register your models here.

admin.site.register(ArtaUser, ArtaUserAdmin)
