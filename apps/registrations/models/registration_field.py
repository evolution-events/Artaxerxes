import reversion
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from konst import Constant, Constants
from konst.models.fields import ConstantChoiceCharField

from arta.common.db import UpdatedAtQuerySetMixin


class RegistrationFieldQuerySet(UpdatedAtQuerySetMixin, models.QuerySet):
    pass


class RegistrationFieldManager(models.Manager.from_queryset(RegistrationFieldQuerySet)):
    def get_by_natural_key(self, eventname, fieldname):
        return self.get(event__name=eventname, name=fieldname)


@reversion.register(follow=('event', 'options'))
class RegistrationField(models.Model):
    """ A field that should get a value during registration for a specific event.  """

    types = Constants(
        Constant(SECTION='section', label=_('Section')),
        Constant(CHOICE='choice', label=_('Choice')),
        Constant(RATING5='rating5', label=_('Rating (1-5)')),
        Constant(STRING='string', label=_('String (single line)')),
        Constant(TEXT='text', label=_('Text (multiline)')),
        Constant(IMAGE='image', label=_('Image')),
        Constant(CHECKBOX='checkbox', label=_('Checkbox')),
        Constant(UNCHECKBOX='uncheckbox', label=_('Checkbox (checked by default)')),
    )

    event = models.ForeignKey('events.Event', related_name='registration_fields', on_delete=models.CASCADE)
    order = models.IntegerField(default=1)
    title = models.CharField(max_length=200)
    help_text = models.TextField(blank=True, help_text=_("Can contain HTML"))
    name = models.CharField(max_length=20)
    field_type = ConstantChoiceCharField(max_length=10, constants=types)
    depends = models.ForeignKey('registrations.RegistrationFieldOption', null=True, blank=True,
                                on_delete=models.SET_NULL)
    invite_only = models.ForeignKey('auth.Group', null=True, blank=True, on_delete=models.SET_NULL)
    allow_change_until = models.DateField(
        null=True, blank=True,
        help_text=_('This field can be changed until (including) this date. If empty, registrations cannot be '
                    'changed.'),
    )
    required = models.BooleanField(default=True)
    is_kitchen_info = models.BooleanField(default=False, help_text=_("This field should appear in the kitchen info."))

    created_at = models.DateTimeField(verbose_name=_('Creation timestamp'), auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name=_('Last update timestamp'), auto_now=True)

    objects = RegistrationFieldManager()

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.event.name, self.name)

    @cached_property
    def allow_change(self):
        return self.allow_change_until and timezone.now().date() <= self.allow_change_until

    class Meta:
        verbose_name = _('registration field')
        verbose_name_plural = _('registration fields')
        ordering = ('order', 'id')

        constraints = [
            models.UniqueConstraint(fields=['event', 'name'], name='unique_name_for_event'),
        ]
