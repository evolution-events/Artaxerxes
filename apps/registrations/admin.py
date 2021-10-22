import reversion
from django.contrib import admin, messages
from django.db import transaction
from django.db.models.functions import Concat
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from hijack_admin.admin import HijackRelatedAdminMixin
from reversion.admin import VersionAdmin

from apps.events.models import Event
from apps.payments.admin import PaymentInline
from apps.people.models import ArtaUser

from .models import Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue


class LimitDependsMixin:
    """
    Mixin intended to limit the choices for a ForeignKey field in the admin based on another field.

    This is based on https://stackoverflow.com/a/29455444/740048 but slightly generalized. This can probably be made
    even more general (by doing the actual filter configuration in the Admin classes instead, or in a function that
    returns a dynamic mixin).
    """

    def get_form(self, request, obj=None, **kwargs):
        """ Called for ModelAdmin instances """
        self.instance = obj
        return super().get_form(request, obj=obj, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        """ Called for InlineModelAdmin instances """
        self.instance = obj
        return super().get_formset(request, obj=obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # For the "depends" foreignkey, only offer options that are associated with the same event.
        if db_field.name == 'depends' and self.instance:
            # Note that for inline admins, self.instance is the parent instance, not the per-inline-row instance. Since
            # a single form is shared by all inline rows, we are called only once and can only filter based on the
            # parent (which is ok for this particular case).
            if isinstance(self.instance, Event):
                check = {'field__event': self.instance}
            elif isinstance(self.instance, RegistrationField):
                check = {'field__event': self.instance.event}
            elif isinstance(self.instance, RegistrationFieldOption):
                check = {'field__event': self.instance.field.event}
            else:
                raise AssertionError()
            objects = db_field.remote_field.model.objects
            kwargs['queryset'] = objects.filter(**check)
        return super().formfield_for_foreignkey(db_field, request=request, **kwargs)


class RegistrationFieldInline(LimitDependsMixin, admin.TabularInline):
    model = RegistrationField
    extra = 0
    # Show edit link for fields, to allow editing options for the field
    show_change_link = True
    prepopulated_fields = {"name": ("title",)}


class RegistrationFieldValueInline(admin.TabularInline):
    model = RegistrationFieldValue
    extra = 0


class CustomRelatedFieldListFilter(admin.filters.RelatedFieldListFilter):
    """ Related field filter that uses a customized string for the empty option (instead of the default -). """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_value_display = _('None')


# TODO: This should probably use a intermediate view to ask the target status, do additional limitation on acceptable
# status changes and do additional actions, such as updating the "full" statuses (and probably delegate the status
# changes to a service).
def change_status_action(old, new):
    """ Helper to generate status change actions """
    def action(modeladmin, request, queryset):
        with transaction.atomic():
            if queryset.exclude(status=old).exists():
                modeladmin.message_user(
                    request,
                    'Not all selected registrations in {} state'.format(old.id),
                    messages.ERROR,
                )
            else:
                with reversion.create_revision():
                    reversion.set_user(request.user)
                    reversion.set_comment(_("Updated registration status to {} via admin.".format(new.id)))
                    for reg in queryset:
                        reg.status = new
                        reg.save()
    action.short_description = 'Change {} registration to {}'.format(old.id, new.id)
    action.__name__ = '{}_to_{}'.format(old.id, new.id)
    return action


@admin.register(Registration)
class RegistrationAdmin(HijackRelatedAdminMixin, VersionAdmin):
    list_display = (
        'event_display_name', 'user_name', 'status', 'registered_at_milliseconds', 'selected_options', 'hijack_field',
    )
    # add a search field to quickly search by name and title
    search_fields = [
        'user__first_name', 'user__last_name', 'event__title', 'event__series__name', 'options__string_value',
        'options__option__title',
    ]
    list_select_related = ['user', 'event__series']
    list_filter = ['status', 'event', ('user__groups', CustomRelatedFieldListFilter)]
    inlines = [PaymentInline, RegistrationFieldValueInline]

    actions = [
        'make_mailing_list',
        change_status_action(Registration.statuses.PENDING, Registration.statuses.REGISTERED),
        change_status_action(Registration.statuses.PENDING, Registration.statuses.CANCELLED),
        change_status_action(Registration.statuses.PENDING, Registration.statuses.WAITINGLIST),
    ]

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).prefetch_options()

    def registered_at_milliseconds(self, obj):
        tz = timezone.get_current_timezone()
        if obj.registered_at:
            localtime = obj.registered_at.astimezone(tz)
            millis = localtime.microsecond / 1000
            return localtime.strftime("%d %b %Y %H:%M:%S.{millis:03}").format(millis=int(millis))
        else:
            return ''

    registered_at_milliseconds.short_description = _("Registered at")
    registered_at_milliseconds.admin_order_field = 'registered_at'

    def event_display_name(self, obj):
        return obj.event.display_name()
    event_display_name.short_description = _("Event")
    # TODO: This hardcodes info about how event.display_name works, but Django cannot seem to derive this
    # automatically by referencing to the computed field here
    event_display_name.admin_order_field = Concat('event__name', 'event__title')

    def user_name(self, obj):
        return obj.user.full_name
    user_name.short_description = _("User")
    # TODO: This hardcodes info about how user.full_name works, but Django cannot seem to derive this
    # automatically by referencing to the computed field here
    user_name.admin_order_field = Concat('user__first_name', 'user__last_name')

    def selected_options(self, obj):
        return format_html_join(mark_safe("<br>"), "{}={}", ((value.field, value) for value in obj.options.all()))
    selected_options.short_description = _("Selected Options")
    selected_options.allow_tags = True

    def make_mailing_list(self, request, queryset):
        users = ArtaUser.objects.filter(registrations__in=queryset).distinct()
        return HttpResponse(
            "\n".join("{} <{}>,".format(u.full_name, u.email) for u in users),
            content_type="text/plain; charset=utf-8",
        )


class RegistrationFieldOptionInline(LimitDependsMixin, admin.TabularInline):
    model = RegistrationFieldOption
    extra = 0


@admin.register(RegistrationField)
class RegistratFieldAdmin(LimitDependsMixin, VersionAdmin):
    inlines = [RegistrationFieldOptionInline]
    prepopulated_fields = {"name": ("title",)}


@admin.register(RegistrationFieldOption)
class RegistratFieldOptionAdmin(LimitDependsMixin, VersionAdmin):
    pass


@admin.register(RegistrationFieldValue)
class RegistratFieldValueAdmin(VersionAdmin):
    pass
