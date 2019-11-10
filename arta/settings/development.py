# Python imports
from os.path import join

from .common import *

# ##### DEBUG CONFIGURATION ###############################
DEBUG = True

# allow all hosts during development
ALLOWED_HOSTS = ['*']

# adjust the minimal login
LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'account_login'

# ##### EMAIL CONFIGURATION ###############################
DEFAULT_FROM_EMAIL = "artaxerxes-test@evolution-events.nl"

# ##### DATABASE CONFIGURATION ############################
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': join(PROJECT_ROOT, 'run', 'dev.sqlite3'),
    },
}

# ##### APPLICATION CONFIGURATION #########################

INSTALLED_APPS = DEFAULT_APPS + [
    'debug_toolbar',
]

FIXTURE_DIRS = [
    join(PROJECT_ROOT, 'fixtures'),
]

# Debug toolbar must be as early as possible, but after things that encode, such as gzip (which we do not use
# currently, so inserting at the start is probably good enough).
MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# Used by debug toolbar
INTERNAL_IPS = [
    '127.0.0.1',
]
