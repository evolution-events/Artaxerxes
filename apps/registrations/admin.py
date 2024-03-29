import reversion
from django.contrib import admin, messages
from django.db import transaction
from django.db.models.functions import Concat
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from hijack_admin.admin import HijackRelatedAdminMixin
from konst.models.fields import ConstantChoiceCharField
from reversion.admin import VersionAdmin

from apps.events.models import Event
from apps.payments.admin import AddPaymentInline, PaymentInline
from apps.people.models import ArtaUser
from arta.common.admin import LimitForeignKeyOptionsMixin

from .models import (Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue,
                     RegistrationPriceCorrection)


class LimitDependsMixin(LimitForeignKeyOptionsMixin):
    """ Mixin intended to limit choices for the depends field based on the event. """

    def get_foreignkey_limits(self, fieldname):
        if fieldname == 'depends':
            return ('field__event', {Event: '', RegistrationField: 'event', RegistrationFieldOption: 'field__event'})
        return super().get_foreignkey_limits(fieldname)


class RegistrationFieldInline(LimitDependsMixin, admin.TabularInline):
    model = RegistrationField
    extra = 0
    # Show edit link for fields, to allow editing options for the field
    show_change_link = True
    prepopulated_fields = {"name": ("title",)}


class RegistrationFieldValueInline(admin.TabularInline):
    model = RegistrationFieldValue
    extra = 0
    # Disallow editing inline, because only the regular admin can properly limit the choices
    readonly_fields = ('option', 'field', 'string_value', 'file_value', 'active')
    fields = ('field', 'option', 'string_value', 'file_value', 'active')
    show_change_link = True

    # Disable add permission to defer adding to the AddRegistrationFieldValueInline below
    def has_add_permission(self, request):
        return False


class AddRegistrationFieldValueInline(LimitForeignKeyOptionsMixin, admin.TabularInline):
    # Extra inline just for adding new values, which does not have all values readonly.
    # This just allows setting the field when adding a new item, deferring setting the values to the regular change
    # value (which has better limiting of choices).
    model = RegistrationFieldValue
    extra = 0
    fields = ('field',)

    def get_foreignkey_limits(self, fieldname):
        if fieldname == 'field':
            return ('event', {Registration: 'event'})
        return super().get_foreignkey_limits(fieldname)

    # Disable change/view permission to prevent displaying existing items here
    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return False


class RegistrationPriceCorrectionInline(admin.TabularInline):
    model = RegistrationPriceCorrection
    extra = 1


class CustomRelatedFieldListFilter(admin.filters.RelatedFieldListFilter):
    """ Related field filter that uses a customized string for the empty option (instead of the default -). """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_value_display = _('None')


def annotation_list_filter(field_name, field):
    """
    Generate a filter class that can be used to filter on to-be annotated values.

    This wraps builtin Django filter classes to prevent code duplication, but only works with fields that have a
    limited set of choices, since the AllValuesFieldListFilter that is used for other field types insists on looking up
    the field on the model class...

    This is a bit of a hack, if annotations could be defined on the model as "computed fields" (i.e.
    https://code.djangoproject.com/ticket/28822), then this class would no longer be needed.
    """
    class AnnotationListFilter(admin.filters.ListFilter):
        def __init__(self, *args, **kwargs):
            self.filter = admin.filters.FieldListFilter.create(field, *args, **kwargs, field_path=field_name)
            self.title = self.filter.title

        def has_output(self):
            return self.filter.has_output()

        def choices(self, changelist):
            return self.filter.choices(changelist)

        def queryset(self, request, queryset):
            return self.filter.queryset(request, queryset)

        def expected_parameters(self):
            return self.filter.expected_parameters()
    return AnnotationListFilter


def registration_field_list_filter(field):
    """ Generate a filter class that can be used to filter Registrations on their associated RegistrationFields. """

    class RegistrationFieldListFilter(admin.SimpleListFilter):
        title = field.title
        parameter_name = f'registration_field_{field.name}'

        def lookups(self, request, model_admin):
            # We cannot apply all filters (if any) yet, since we have insufficient info here (the list of filters is
            # still being built). But we can shortcut and apply at least the event filter that caused this registration
            # field filter to be shown.
            registrations = model_admin.get_queryset(request).filter(event=field.event_id)
            values = RegistrationFieldValue.objects.filter(registration__in=registrations).filter(field=field)

            if field.field_type.CHOICE:
                result = [(option.pk, option.title) for option in field.options.all()]
            elif field.field_type.CHECKBOX or field.field_type.UNCHECKBOX:
                result = [
                    (RegistrationFieldValue.CHECKBOX_VALUES[True], _('Yes')),
                    (RegistrationFieldValue.CHECKBOX_VALUES[False], _('No')),
                ]
            elif field.field_type.STRING:
                result = [
                    (value.string_value, value.string_value or _("Empty"))
                    for value in values
                ]
            # TODO: Implement RATING5? TEXT and IMAGE probably do not make sense
            else:
                return None

            if registrations.exclude(options__field=field).exists():
                # Registrations exist that do *not* have this field
                result.append(("VALUE_MISSING", _("Missing")))

            return result

        def queryset(self, request, queryset):
            value = self.value()
            if value == "VALUE_MISSING":
                return queryset.exclude(options__field=field)
            elif value is not None:
                if field.field_type.CHOICE:
                    return queryset.filter(options__field=field, options__option=value)
                elif field.field_type.CHECKBOX or field.field_type.UNCHECKBOX or field.field_type.STRING:
                    return queryset.filter(options__field=field, options__string_value=value)
                else:
                    raise ValueError("Passed filter value for unsupported field type?")
            else:
                return queryset

    return RegistrationFieldListFilter


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
        'event_display_name', 'user_name', 'status', 'registered_at_milliseconds', 'selected_options', 'price',
        'payment_status', 'hijack_field',
    )
    # add a search field to quickly search by name and title
    search_fields = [
        'user__first_name', 'user__last_name', 'event__title', 'event__series__name', 'options__string_value',
        'options__option__title',
    ]
    list_select_related = ['user', 'event__series']
    list_filter = [
        'status', 'event', ('user__groups', CustomRelatedFieldListFilter),
        annotation_list_filter('payment_status', ConstantChoiceCharField(
            constants=Registration.payment_statuses,
            verbose_name=_('Payment status'),
        )),
    ]

    inlines = [
        PaymentInline, AddPaymentInline, RegistrationFieldValueInline, AddRegistrationFieldValueInline,
        RegistrationPriceCorrectionInline,
    ]

    actions = [
        'make_mailing_list',
        'add_users_to_group',
        change_status_action(Registration.statuses.PENDING, Registration.statuses.REGISTERED),
        change_status_action(Registration.statuses.PENDING, Registration.statuses.CANCELLED),
        change_status_action(Registration.statuses.PENDING, Registration.statuses.WAITINGLIST),
        change_status_action(Registration.statuses.WAITINGLIST, Registration.statuses.CANCELLED),
    ]

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).prefetch_active_options().with_payment_status()

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

    # The startup check tool does no consider annotations, only fields, properties and admin methods so make it happy
    def price(self, obj):
        return obj.price

    # The startup check tool does no consider annotations, only fields, properties and admin methods so make it happy
    def payment_status(self, obj):
        return obj.payment_status.label

    def selected_options(self, obj):
        return format_html_join(mark_safe("<br>"), "{}={}", ((value.field, value) for value in obj.active_options))
    selected_options.short_description = _("Selected Options")
    selected_options.allow_tags = True

    def add_users_to_group(self, request, queryset):
        userids = ArtaUser.objects.filter(registrations__pk__in=queryset).values_list('pk', flat=True)
        return redirect('admin:add_users_to_group', ','.join(map(str, userids)))

    def make_mailing_list(self, request, queryset):
        users = ArtaUser.objects.filter(registrations__in=queryset).distinct()
        return HttpResponse(
            "\n".join("{} <{}>,".format(u.full_name, u.email) for u in users),
            content_type="text/plain; charset=utf-8",
        )

    def get_list_filter(self, request):
        filters = super().get_list_filter(request)

        # This is a bit of a hack, since it bypasss the normal ListFilter abstractions and peeks at the GET params
        # directly (and making assumptions about the parameter name), but the relevant info is not otherwise known or
        # accessible from here, so this is probably the best we can do...
        event_id = request.GET.get('event__id__exact', None)
        if event_id is not None:
            qs = Event.objects.prefetch_related('registration_fields').prefetch_related('registration_fields__options')
            event = qs.get(pk=event_id)
            return filters + [
                registration_field_list_filter(field)
                for field in event.registration_fields.all()
            ]
        else:
            return filters


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
class RegistratFieldValueAdmin(LimitForeignKeyOptionsMixin, VersionAdmin):
    fields = ('registration', 'field', 'option', 'string_value', 'file_value', 'active')
    # TODO: Instead of changing values directly, maybe old values should be made inactive and replaced by new values?

    def get_foreignkey_limits(self, fieldname):
        if fieldname == 'field':
            return ('event', {RegistrationFieldValue: 'registration__event'})
        elif fieldname == 'option':
            return ('field', {RegistrationFieldValue: 'field'})
        return super().get_foreignkey_limits(fieldname)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['field', 'registration', 'active']
        else:
            return ['active']
