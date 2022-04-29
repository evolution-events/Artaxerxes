from django.contrib import admin
from reversion.admin import VersionAdmin

from apps.registrations.models import Registration

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(VersionAdmin):
    list_display = ('registration', 'timestamp', 'type', 'amount', 'status', 'mollie_status')

    def get_readonly_fields(self, request, obj=None):
        fields = ['mollie_id', 'mollie_status']
        if obj and obj.mollie_id:
            fields += ['amount', 'status']
        return fields

    def has_delete_permission(self, request, obj=None):
        # Disallow deleting mollie payments
        if obj and obj.mollie_id:
            return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Ensure this dropdown is rendered with appropriate select_related's as used by the  __str__ method
        # TODO: Would be better to do this centrally in some way. Maybe a mixin that handles all foreignkeys to models
        # that have similar __str__ methods? See also https://code.djangoproject.com/ticket/33208#ticket
        if db_field.name == "registration":
            kwargs['queryset'] = Registration.objects.all().select_related('user', 'event')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        # Only allow COMPLETED payments in the admin, other statuses are reserved for automatic payments
        if db_field.name == "status":
            kwargs['choices'] = [(k.v, k.label) for k in [Payment.statuses.COMPLETED]]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

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
    readonly_fields = ['timestamp', 'amount', 'status', 'mollie_id', 'mollie_status']
    can_delete = False
    show_change_link = True

    # With all fields readonly, adding new entries is not meaningful
    # TODO: Can we make this work anyway? Maybe only make existing objects readonly, or only make amount/status
    # readonly on objects with mollie_id?
    def has_add_permission(self, *args, **kwargs):
        return False
