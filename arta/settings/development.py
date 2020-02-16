# Python imports
import os
from os.path import join

import airplane

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
BCC_EMAIL_TO = []

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
    'airplane',
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
# ##### Airplane static files ###############################

AIRPLANE_CACHE = join(PROJECT_ROOT, airplane.CACHE_DIR)
STATICFILES_DIRS += (
    AIRPLANE_CACHE,
)

# Create cache directory. It seems that the debug_toolbar tries to access all STATICFILES_DIRS before airplan gets a
# chance to create it.
os.makedirs(AIRPLANE_CACHE, exist_ok=True)

# To use airplane, run with BUILD_CACHE to download files on every request (only when DEBUG=true), then change to
# USE_CACHE when offline to use cached versions.
# AIRPLANE_MODE = airplane.BUILD_CACHE
# AIRPLANE_MODE = airplane.USE_CACHE
