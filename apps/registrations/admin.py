from django.contrib import admin
from django.utils import timezone
from django.utils.translation import ugettext_lazy
from reversion.admin import VersionAdmin

from apps.events.models import Event

from .models import Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue


class RegistrationFieldInline(admin.TabularInline):
    model = RegistrationField
    extra = 0
    # Show edit link for fields, to allow editing options for the field
    show_change_link = True
    prepopulated_fields = {"name": ("title",)}


@admin.register(Registration)
class RegistrationAdmin(VersionAdmin):
    list_display = ('event_display_name', 'user_name', 'status', 'registered_at_milliseconds')
    # add a search field to quickly search by name and title
    search_fields = ['user__first_name', 'user__last_name', 'event__title', 'event__series__name']
    list_select_related = ['user', 'event__series']
    list_filter = ['status']

    def registered_at_milliseconds(self, obj):
        tz = timezone.get_current_timezone()
        localtime = obj.registered_at.astimezone(tz)
        millis = localtime.microsecond / 1000

        return localtime.strftime("%d %b %Y %H:%M:%S.{millis:03}").format(millis=int(millis))
    registered_at_milliseconds.short_description = ugettext_lazy("Registered at")

    def event_display_name(self, obj):
        return obj.event.display_name()
    event_display_name.short_description = ugettext_lazy("Event")

    def user_name(self, obj):
        return obj.user.get_full_name()
    user_name.short_description = ugettext_lazy("User")


class RegistrationFieldOptionInline(admin.TabularInline):
    model = RegistrationFieldOption
    extra = 0


@admin.register(RegistrationField)
class RegistratFieldAdmin(VersionAdmin):
    inlines = [RegistrationFieldOptionInline]
    prepopulated_fields = {"name": ("title",)}


@admin.register(RegistrationFieldOption)
class RegistratFieldOptionAdmin(VersionAdmin):
    pass


@admin.register(RegistrationFieldValue)
class RegistratFieldValueAdmin(VersionAdmin):
    pass
