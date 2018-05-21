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


# ##### DATABASE CONFIGURATION ############################
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': join(PROJECT_ROOT, 'run', 'dev.sqlite3'),
    },
}

# ##### APPLICATION CONFIGURATION #########################

INSTALLED_APPS = DEFAULT_APPS

FIXTURE_DIRS = [
    join(PROJECT_ROOT, 'fixtures'),
]
