import import_export.admin
import import_export.fields
import import_export.resources
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import path
from django.utils.translation import ugettext_lazy as _
from hijack_admin.admin import HijackUserAdminMixin
from reversion.admin import VersionAdmin

from .adminviews import AddUsersToGroupView
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


class EmailAddressInline(admin.TabularInline):
    model = EmailAddress
    extra = 0


class ArtaUserResource(import_export.resources.ModelResource):
    secondary_emails = import_export.fields.Field()

    def get_queryset(self):
        return super().get_queryset().select_related('emailaddress_set')

    def dehydrate_secondary_emails(self, user):
        secondary_qs = user.emailaddress_set.filter(
            primary=False,
            verified=True,
        )
        return ','.join(secondary_qs.values_list('email', flat=True))

    class Meta:
        model = ArtaUser
        fields = ('first_name', 'last_name', 'email', 'secondary_emails')
        # https://github.com/django-import-export/django-import-export/issues/1191
        export_order = fields


@admin.register(ArtaUser)
class ArtaUserAdmin(import_export.admin.ExportMixin, UserAdmin, HijackUserAdminMixin, VersionAdmin):
    inlines = (AddressInline, EmergencyContactInline, EmailAddressInline)
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'hijack_field')
    search_fields = ('first_name', 'last_name', 'email')
    list_filter = UserAdmin.list_filter + ('consent_announcements_nl', 'consent_announcements_en')
    ordering = ('email',)
    actions = ['make_mailing_list', 'add_users_to_group']
    resource_class = ArtaUserResource  # For ExportMixin

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

    def get_urls(self):
        # Prepend new path so it is before the catchall that ModelAdmin adds
        return [
            path('<path:userids>/add-to-group/',
                 self.admin_site.admin_view(AddUsersToGroupView.as_view(admin_site=self.admin_site)),
                 name='add_users_to_group'),
        ] + super().get_urls()

    def add_users_to_group(self, request, queryset):
        userids = queryset.values_list('pk', flat=True)
        return redirect('admin:add_users_to_group', ','.join(map(str, userids)))

    def make_mailing_list(self, request, queryset):
        return HttpResponse(
            "\n".join("{} <{}>,".format(u.full_name, u.email) for u in queryset),
            content_type="text/plain; charset=utf-8",
        )


class GroupMemberInline(admin.TabularInline):
    model = ArtaUser.groups.through


# Replace the original Group admin.
admin.site.unregister(Group)


@admin.register(Group)
class CustomGroupAdmin(GroupAdmin):
    inlines = (GroupMemberInline,)
