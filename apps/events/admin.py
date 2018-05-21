from django.contrib import admin
from reversion.admin import VersionAdmin
from django.utils.translation import gettext as _
from django.utils.translation import ugettext_lazy

from .models import Event, Series, Registration


@admin.register(Event)
class EventAdmin(VersionAdmin):
    list_display = ('event_title', 'start_date', 'end_date', 'location_name')

    def event_title(self, obj):
        if obj.series:
                return _('%(series)s: %(title)s') % {'series': obj.series, 'title': obj.title}
        else:
                return obj.title
    event_title.short_description = ugettext_lazy("Series: title")


@admin.register(Registration)
class RegistrationAdmin(VersionAdmin):
    list_display = ('event_title', 'user_name', 'status')
    # add a search field to quickly search by name and title
    search_fields = ['user__first_name', 'user__last_name', 'event__title', 'event__series__name']
    list_select_related = ['user', 'event__series']
    list_filter = ['status']

    def event_title(self, obj):
        if obj.event.series:
                return _('%(series)s: %(title)s') % {'series': obj.event.series, 'title': obj.event.title}
        else:
                return obj.event.title
    event_title.short_description = ugettext_lazy("Series: title")

    def user_name(self, obj):
            return obj.user.get_full_name()
    user_name.short_description = ugettext_lazy("User")


@admin.register(Series)
class SeriesAdmin(VersionAdmin):
        pass
