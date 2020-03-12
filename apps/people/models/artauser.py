import reversion
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


class ArtaUserManager(BaseUserManager):
    def get_by_natural_key(self, email):
        return self.get(email=email)


# For reference to this model, see
# https://docs.djangoproject.com/en/2.1/topics/auth/customizing/#referencing-the-user-model
@reversion.register()
class ArtaUser(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    email = models.EmailField(_('email address'), unique=True)

    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )

    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.',
        ),
    )

    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    consent_announcements = models.BooleanField(
        verbose_name=_('Send updates'),
        help_text=_('Keep me updated about new events. You will receive at most a few e-mails each year'),
        default=False,
    )

    objects = ArtaUserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = '%s %s' % (self.first_name, self.last_name)
        full_name = full_name.strip()
        if not full_name:
            full_name = self.email
        return full_name

    def __str__(self):
        return self.get_full_name()

    def natural_key(self):
        return (self.email,)
