from django.contrib import admin
from django.utils import timezone
from django.utils.translation import ugettext_lazy
from reversion.admin import VersionAdmin

from apps.events.models import Event

from .models import Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue


class LimitDependsMixin:
    """
    Mixin intended to limit the choices for a ForeignKey field in the admin based on another field.

    This is based on https://stackoverflow.com/a/29455444/740048 but slightly generalized. This can probably be made
    even more general (by doing the actual filter configuration in the Admin classes instead, or in a function that
    returns a dynamic mixin).
    """

    def get_form(self, request, obj=None, **kwargs):
        """ Called for ModelAdmin instances """
        self.instance = obj
        return super().get_form(request, obj=obj, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        """ Called for InlineModelAdmin instances """
        self.instance = obj
        return super().get_formset(request, obj=obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        # For the "depends" foreignkey, only offer options that are associated with the same event.
        if db_field.name == 'depends' and self.instance:
            # Note that for inline admins, self.instance is the parent instance, not the per-inline-row instance. Since
            # a single form is shared by all inline rows, we are called only once and can only filter based on the
            # parent (which is ok for this particular case).
            if isinstance(self.instance, Event):
                check = {'field__event': self.instance}
            elif isinstance(self.instance, RegistrationField):
                check = {'field__event': self.instance.event}
            elif isinstance(self.instance, RegistrationFieldOption):
                check = {'field__event': self.instance.field.event}
            else:
                raise AssertionError()
            objects = db_field.remote_field.model.objects
            kwargs['queryset'] = objects.filter(**check)
        return super().formfield_for_foreignkey(db_field, request=request, **kwargs)


class RegistrationFieldInline(LimitDependsMixin, admin.TabularInline):
    model = RegistrationField
    extra = 0
    # Show edit link for fields, to allow editing options for the field
    show_change_link = True
    prepopulated_fields = {"name": ("title",)}


class RegistrationFieldValueInline(admin.TabularInline):
    model = RegistrationFieldValue
    extra = 0


class CustomRelatedFieldListFilter(admin.filters.RelatedFieldListFilter):
    """ Related field filter that uses a customized string for the empty option (instead of the default -). """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_value_display = ugettext_lazy('None')


@admin.register(Registration)
class RegistrationAdmin(VersionAdmin):
    list_display = ('event_display_name', 'user_name', 'status', 'registered_at_milliseconds')
    # add a search field to quickly search by name and title
    search_fields = ['user__first_name', 'user__last_name', 'event__title', 'event__series__name']
    list_select_related = ['user', 'event__series']
    list_filter = ['status', 'event', ('user__groups', CustomRelatedFieldListFilter)]
    inlines = [RegistrationFieldValueInline]

    def registered_at_milliseconds(self, obj):
        tz = timezone.get_current_timezone()
        if obj.registered_at:
            localtime = obj.registered_at.astimezone(tz)
            millis = localtime.microsecond / 1000
            return localtime.strftime("%d %b %Y %H:%M:%S.{millis:03}").format(millis=int(millis))
        else:
            return ''

    registered_at_milliseconds.short_description = ugettext_lazy("Registered at")

    def event_display_name(self, obj):
        return obj.event.display_name()
    event_display_name.short_description = ugettext_lazy("Event")

    def user_name(self, obj):
        return obj.user.get_full_name()
    user_name.short_description = ugettext_lazy("User")


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
class RegistratFieldValueAdmin(VersionAdmin):
    pass
