from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Event, Series


@admin.register(Event)
class EventAdmin(VersionAdmin):
    list_display = ('display_name', 'start_date', 'end_date', 'location_name')


@admin.register(Series)
class SeriesAdmin(VersionAdmin):
    pass
