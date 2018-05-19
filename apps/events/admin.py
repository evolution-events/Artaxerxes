from django.contrib import admin
from .models import Series, Event
from django.utils.translation import gettext as _, ugettext_lazy


class EventAdmin(admin.ModelAdmin):
    list_display = ('event_title', 'start_date', 'end_date', 'location_name')

    def event_title(self, obj):
        if obj.series:
                return _('%(series)s: %(title)s') % {'series': obj.series, 'title': obj.title}
        else:
                return obj.title
    event_title.short_description = ugettext_lazy("Series: title")


# Register your models here.

admin.site.register(Series)
admin.site.register(Event, EventAdmin)
