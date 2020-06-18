# Python imports
import re
import sys
from os.path import abspath, basename, dirname, join, normpath

from django.core import serializers
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _

# Import local_settings, if they exist
try:
    from .local_settings import *
except ImportError:
    pass


# Work around Django bug https://code.djangoproject.com/ticket/31051
# This effectively disables natural key dependency sorting for serialization, since that is not actually really
# required in most cases (loaddata already handles unsorted lists, and test-db serialization does not use natural
# keys).
def _sort_dependencies(app_list):
    ret = []
    for app_config, model_list in app_list:
        if model_list is None:
            model_list = app_config.get_models()
        ret.extend(model_list)
    return ret


try:
    # This backports (the essential parts of) commit 1fc2c70f76 (Fixed #30593 -- Added support for check constraints on
    # MariaDB 10.2+). This allows using CheckConstraints on sufficiently new Mariadb versions. Without this, the check
    # constraints were actually already used, but the db check would show a warning that they woudl not be, and a
    # violation would throw an OperationalError instead of an IntegrityError.
    from django.db.backends.mysql.base import CursorWrapper
    from django.db.backends.mysql.features import DatabaseFeatures
    DatabaseFeatures.supports_column_check_constraints = property(
        lambda self: self.connection.mysql_is_mariadb and self.connection.mysql_version >= (10, 2, 1),
    )
    DatabaseFeatures.supports_table_check_constraints = property(
        lambda self: self.connection.mysql_is_mariadb and self.connection.mysql_version >= (10, 2, 1),
    )
    CursorWrapper.codes_for_integrityerror += (4025,)
except ImproperlyConfigured:
    # If mysqlclient is not installed, importing the mysql backend raises an ImportError, but then this workaround will
    # not be relevant anyway, so just ignore it.
    pass

serializers.sort_dependencies = _sort_dependencies

# ##### PATH CONFIGURATION ################################

# fetch Django's project directory
DJANGO_ROOT = dirname(dirname(abspath(__file__)))

# fetch the project_root
PROJECT_ROOT = dirname(DJANGO_ROOT)

# the name of the whole site
SITE_NAME = basename(DJANGO_ROOT)

# the site ID for contrib.sites
SITE_ID = 1

# collect static files here
STATIC_ROOT = join(PROJECT_ROOT, 'run', 'static')

# collect media files here
MEDIA_ROOT = join(PROJECT_ROOT, 'run', 'media')

# look for static assets here
STATICFILES_DIRS = [
    join(PROJECT_ROOT, 'static'),
]

# look for templates here
# This is an internal setting, used in the TEMPLATES directive
PROJECT_TEMPLATES = [
    join(PROJECT_ROOT, 'templates'),
]

# ##### Internationalization ##############################
LANGUAGE_CODE = 'en'
TIME_ZONE = 'Europe/Amsterdam'

# Internationalization
USE_I18N = False

# Localisation
USE_L10N = True

# enable timezone awareness by default
USE_TZ = True

# This list of languages will be provided
LANGUAGES = (
    ('nl', _('Dutch')),
    ('en', _('English')),
)

MONETARY_CURRENCY = '€'
MONETARY_DECIMAL_PLACES = 2
MONETARY_MAX_DIGITS = 12

FORMAT_MODULE_PATH = [
    'arta.locales',
]

# Allow entry of local numbers as well
PHONENUMBER_DEFAULT_REGION = "NL"
# Display numbers with explicit country code, but also include spaces (unlike the default E164 format, which has
# country code and no spaces).
PHONENUMBER_DEFAULT_FORMAT = "INTERNATIONAL"

# ##### APPLICATION CONFIGURATION #########################

# these are the apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'reversion',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # TODO: social accounts weer aanzetten als we ze handig hebben gemaakt
    # 'allauth.socialaccount.providers.google',
    'apps.people.apps.PeopleConfig',
    'apps.events.apps.EventsConfig',
    'apps.registrations.apps.RegistrationsConfig',
    'apps.core.apps.CoreConfig',
    'phonenumber_field',
    'airplane',
    'hijack',
    'hijack_admin',
    'compat',
]

# Middlewares
MIDDLEWARE = [
    'django.middleware.common.BrokenLinkEmailsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# template stuff
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': PROJECT_TEMPLATES,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# #### USER CONFIGURATION #################################
AUTH_USER_MODEL = 'people.ArtaUser'

AUTHENTICATION_BACKENDS = (
    # Allauth for login by e-mail or using external parties
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_AUTHENTICATION_METHOD = 'email'
# Reduce the max email address length. According to RFCs, addresses up
# to 254 characters (or bytes, a bit unclear) are valid, but such long
# addresses are not actually used in practice. Since e-mailaddress is
# used as a database unique index, it could help performance to limit it
# a bit (also, the default runs into maximum key size limits on older
# versions of Mysql/Mariadb).
ACCOUNT_EMAIL_MAX_LENGTH = 64
# Automatically login people after email-confirmation after signup.
# For security, this only works in the same browse session as the initial signup.
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_SIGNUP_FORM_CLASS = 'apps.core.forms.SignupFormBase'

LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'account_login'

# ##### SECURITY CONFIGURATION ############################

# We store the secret key here
# The required SECRET_KEY is fetched at the end of this file
SECRET_FILE = normpath(join(PROJECT_ROOT, 'run', 'SECRET.key'))

# ##### EMAIL CONFIGURATION ################################
DEFAULT_FROM_EMAIL = 'registrations@evolution-events.nl'
BCC_EMAIL_TO = ['registrations@evolution-events.nl']
SERVER_EMAIL = 'registrations@evolution-events.nl'
EMAIL_SUBJECT_PREFIX = "Evolution Events: "
ACCOUNT_EMAIL_SUBJECT_PREFIX = EMAIL_SUBJECT_PREFIX

# Dispatch e-mail using local sendmail, or equivalent
EMAIL_BACKEND = 'django_sendmail_backend.backends.EmailBackend'
SENDMAIL_BINARY = '/usr/sbin/sendmail'

# ##### DJANGO RUNNING CONFIGURATION ######################

# the default WSGI application
WSGI_APPLICATION = '%s.wsgi.application' % SITE_NAME

# the root URL configuration
ROOT_URLCONF = '%s.urls' % SITE_NAME

# the URL for static files
STATIC_URL = '/static/'

# the URL for media files
MEDIA_URL = '/media/'


# ##### DEBUG CONFIGURATION ###############################
DEBUG = False

# 404 REPORTING ####################################

# These are not reported by the BrokenLinkEmailsMiddleware
IGNORABLE_404_URLS = [
    re.compile(r'.php$'),
]

# ##### DJANGO HIJACK #####################################
HIJACK_USE_BOOTSTRAP = True
# We register admin fields manually
HIJACK_REGISTER_ADMIN = False
# Needed for hijack-admin. TODO: How about CSRF?
HIJACK_ALLOW_GET_REQUESTS = True


# finally grab the SECRET KEY
try:
    SECRET_KEY = open(SECRET_FILE).read().strip()
except IOError:
    try:
        from django.utils.crypto import get_random_string
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!$%&()=+-_'
        SECRET_KEY = get_random_string(50, chars)
        with open(SECRET_FILE, 'w') as f:
            f.write(SECRET_KEY)
    except IOError:
        raise Exception('Could not open %s for writing!' % SECRET_FILE)
