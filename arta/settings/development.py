# Python imports
import os
from os.path import join

import airplane

from .common import *

# ##### DEBUG CONFIGURATION ###############################
DEBUG = True

# ##### DJANGO HIJACK #####################################
HIJACK_USE_BOOTSTRAP = True
# Register admin fields manually
HIJACK_REGISTER_ADMIN = False
# Needed for hijack-admin. TODO: How about CSRF?
HIJACK_ALLOW_GET_REQUESTS = True

# allow all hosts during development
ALLOWED_HOSTS = ['*']

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

INSTALLED_APPS += [
    'debug_toolbar',
    'hijack',
    'hijack_admin',
    'compat',
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

# When DEBUG=True, this causes airplane to automatically cache selected external dependencies and then serve them from
# cache subsequently. There is no cache clear, so if an external resource changes without changing the URL, it should
# be manually removed from the cache (but that should not normally happen).
AIRPLANE_MODE = airplane.AUTO_CACHE
