import import_export.admin
import import_export.fields
import import_export.formats.base_formats
import import_export.resources
from django.contrib import admin
from django.forms.fields import DateTimeField
from reversion.admin import VersionAdmin

from apps.registrations.models import Registration
from arta.common.admin import MonetaryResourceWidget

from .models import Payment


class EventPaymentsResource(import_export.resources.ModelResource):
    """ Resource that can export payments for a single event. """

    id = import_export.fields.Field(attribute='pk')
    registration_id = import_export.fields.Field(attribute='registration__id')
    name = import_export.fields.Field(attribute='registration__user__full_name')
    amount = import_export.fields.Field(attribute='amount', widget=MonetaryResourceWidget)
    status = import_export.fields.Field(attribute='get_status_display')

    mollie_id = import_export.fields.Field(attribute='mollie_id')
    mollie_status = import_export.fields.Field(attribute='mollie_status')

    created_at = import_export.fields.Field(attribute='created_at')
    updated_at = import_export.fields.Field(attribute='updated_at')
    timestamp = import_export.fields.Field(attribute='timestamp')

    def __init__(self, event):
        super().__init__()
        self.event = event

    def get_queryset(self):
        return (
            super().get_queryset()
            .filter(registration__event=self.event)
            .select_related('registration__user')
            .order_by('created_at')
        )

    class Meta:
        model = Payment
        fields = ()  # No additional fields to auto-import from model


class PaymentAdminMixin:
    """ Methods shared between regular and inline admin. """

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Ensure this dropdown is rendered with appropriate select_related's as used by the  __str__ method
        # TODO: Would be better to do this centrally in some way. Maybe a mixin that handles all foreignkeys to models
        # that have similar __str__ methods? See also https://code.djangoproject.com/ticket/33208#ticket
        if db_field.name == "registration":
            kwargs['queryset'] = Registration.objects.filter(
                status__in=Registration.statuses.FINALIZED,
            ).select_related('user', 'event').order_by('user', 'event')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        # Only allow COMPLETED payments in the admin, other statuses are reserved for automatic payments
        if db_field.name == "status":
            kwargs['choices'] = [(k.v, k.label) for k in [Payment.statuses.COMPLETED]]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'timestamp':
            # This uses a regular datetime input instead of split, but with the datewidget so you get just a date
            # picker (manual transactions usually have just a date), but override the format to include a time
            # component so you *can* still input a time if you want.
            kwargs['form_class'] = DateTimeField
            kwargs['widget'] = admin.widgets.AdminDateWidget(format='%Y-%m-%d %H:%M:%S')

        return super().formfield_for_dbfield(db_field, **kwargs)


@admin.register(Payment)
class PaymentAdmin(PaymentAdminMixin, VersionAdmin):
    list_display = ('registration', 'created_at', 'timestamp', 'type', 'amount', 'status', 'mollie_status')

    def get_readonly_fields(self, request, obj=None):
        fields = ['mollie_id', 'mollie_status', 'created_at', 'updated_at']
        if obj and obj.mollie_id:
            fields += ['amount', 'status', 'timestamp']
        return fields

    def has_delete_permission(self, request, obj=None):
        # Disallow deleting mollie payments
        if obj and obj.mollie_id:
            return False
        return super().has_delete_permission(request, obj)

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        qs.select_related('registration', 'registration__user', 'registration__event')
        return qs

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial['status'] = Payment.statuses.COMPLETED
        return initial


class PaymentInline(admin.TabularInline):
    model = Payment
    fk_name = 'registration'

    # Edit and delete can only be done through the PaymentAdmin, which can properly limit editing of mollie payments
    # (in an inline admin, you can only limit based on the containing object, e.g. Registration). This uses readonly
    # fields, since removing change permission also removes the change link.
    readonly_fields = ['created_at', 'timestamp', 'amount', 'status', 'mollie_id', 'mollie_status']
    can_delete = False
    show_change_link = True

    # With all fields readonly, adding new entries is not meaningful
    # TODO: Can we make this work anyway? Maybe only make existing objects readonly, or only make amount/status
    # readonly on objects with mollie_id?
    def has_add_permission(self, *args, **kwargs):
        return False


class AddPaymentInline(PaymentAdminMixin, admin.TabularInline):
    # Extra inline just for adding new values, which does not have all values readonly.
    model = Payment
    extra = 0
    fields = ['created_at', 'timestamp', 'amount', 'status', 'mollie_id', 'mollie_status']
    readonly_fields = ['mollie_id', 'mollie_status', 'created_at', 'updated_at']

    # Disable change/view permission to prevent displaying existing items here
    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return False
