from django.contrib import admin
from reversion.admin import VersionAdmin

from apps.registrations.admin import RegistrationFieldInline

from .models import Event, Series


@admin.register(Event)
class EventAdmin(VersionAdmin):
    list_display = ('display_name', 'start_date', 'end_date', 'location_name')
    inlines = (RegistrationFieldInline,)

    ordering = ('start_date',)
    date_hierarchy = 'start_date'


@admin.register(Series)
class SeriesAdmin(VersionAdmin):
    pass
