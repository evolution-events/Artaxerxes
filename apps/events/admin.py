from django.contrib import admin
from reversion.admin import VersionAdmin
from django.utils.translation import gettext as _
from django.utils.translation import ugettext_lazy

from .models import Event, Series, Registration


@admin.register(Event)
class EventAdmin(VersionAdmin):
    list_display = ('display_name', 'start_date', 'end_date', 'location_name')

@admin.register(Registration)
class RegistrationAdmin(VersionAdmin):
    list_display = ('event_display_name', 'user_name', 'status')
    # add a search field to quickly search by name and title
    search_fields = ['user__first_name', 'user__last_name', 'event__title', 'event__series__name']
    list_select_related = ['user', 'event__series']
    list_filter = ['status']

    def event_display_name(self, obj):
        return obj.event.display_name()
    event_display_name.short_description = ugettext_lazy("Event")

    def user_name(self, obj):
        return obj.user.get_full_name()
    user_name.short_description = ugettext_lazy("User")


@admin.register(Series)
class SeriesAdmin(VersionAdmin):
        pass
