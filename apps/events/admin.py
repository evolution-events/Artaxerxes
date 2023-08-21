import datetime

import import_export.admin
import import_export.fields
import import_export.formats.base_formats
import import_export.resources
from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html
from reversion.admin import VersionAdmin

from apps.registrations.admin import RegistrationFieldInline
from apps.registrations.models import Registration, RegistrationField
from arta.common.admin import MonetaryResourceWidget

from .adminviews import EventCopyFieldsView
from .models import Event, Series


class RegistrationFieldValueField(import_export.fields.Field):
    """ Export field that takes its value from a RegistrationFieldValue. """

    def get_value(self, obj):
        value = obj.active_options_by_name.get(self.attribute, None)
        if value is None:
            return None
        return value.display_value()


class EventRegistrationsResource(import_export.resources.ModelResource):
    """ Resource that can export registrations for a single event, with event-specific RegistrationFields. """

    id = import_export.fields.Field(attribute='pk')
    first_name = import_export.fields.Field(attribute='user__first_name')
    last_name = import_export.fields.Field(attribute='user__last_name')
    email = import_export.fields.Field(attribute='user__email')
    phone_number = import_export.fields.Field(attribute='user__address__phone_number')
    status = import_export.fields.Field(attribute='get_status_display')
    registered_at = import_export.fields.Field(attribute='registered_at')
    payment_status = import_export.fields.Field(attribute='payment_status')
    price = import_export.fields.Field(attribute='price', widget=MonetaryResourceWidget())
    paid = import_export.fields.Field(attribute='paid', widget=MonetaryResourceWidget())

    def __init__(self, event):
        super().__init__()

        self.event = event
        self.fields.update(
            (
                # key
                'option_{}'.format(reg_field.name),
                # value
                RegistrationFieldValueField(column_name=reg_field.name, attribute=reg_field.name),
            )
            for reg_field in event.registration_fields.exclude(field_type=RegistrationField.types.SECTION)
        )

    def get_queryset(self):
        return (
            super().get_queryset()
            .filter(event=self.event)
            .select_related('user')
            .select_related('user__address')
            .prefetch_active_options()
            .with_payment_status()
            .order_by('created_at')
        )

    class Meta:
        model = Registration
        fields = ()  # No additional fields to auto-import from model


@admin.register(Event)
class EventAdmin(VersionAdmin):
    list_display = ('display_name', 'start_date', 'end_date', 'location_name')
    inlines = (RegistrationFieldInline,)
    actions = ['export_active_registrations']

    ordering = ('start_date',)
    date_hierarchy = 'start_date'
    readonly_fields = ('actions_field',)

    def export_active_registrations(self, request, queryset):
        try:
            event = queryset.get()
        except Event.MultipleObjectsReturned:
            self.message_user(
                request=request, level=messages.ERROR,
                message="Registrations for only one event can be exported at the same time",
            )
            return None

        resource = EventRegistrationsResource(event)
        reg_qs = (
            resource.get_queryset()
            .filter(status__in=Registration.statuses.ACTIVE)
            .order_by('registered_at')
        )
        file_format = import_export.formats.base_formats.CSV()
        export_data = file_format.export_data(resource.export(reg_qs))
        response = HttpResponse(export_data, content_type=file_format.get_content_type())
        response['Content-Disposition'] = 'attachment; filename="{}-{}.{}"'.format(
            event.name, datetime.datetime.now().strftime('%Y-%m-%d'), file_format.get_extension(),
        )
        return response

    def get_urls(self):
        # Prepend new path so it is before the catchall that ModelAdmin adds
        return [
            path('<path:pk>/copy-options/',
                 self.admin_site.admin_view(EventCopyFieldsView.as_view(admin_site=self.admin_site)),
                 name='copy_event_fields'),
        ] + super().get_urls()

    def actions_field(self, obj):
        return format_html(
            '<a class="button" href="{}">Copy fields from other event</a>&nbsp;',
            reverse('admin:copy_event_fields', args=[obj.pk]),
        )
    actions_field.short_description = "Event Actions"
    actions_field.allow_tags = True


@admin.register(Series)
class SeriesAdmin(VersionAdmin):
    pass
