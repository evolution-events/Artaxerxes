# for now fetch the development settings only
from .common import *

# turn off all debugging
DEBUG = False

# You will have to determine, which hostnames should be served by Django
ALLOWED_HOSTS = []

# This logs to stdout/stderr, which ends up in the default uwsgi log
# files.
LOGGING = {
    'version': 1,
    # Recommended, otherwise default loggers are disabled but not removed, apparently?
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} - {levelname} - {message}',
            'style': '{',
            # This mimics the (rather interesting) uwsgi data format to
            # get a unified log output
            'datefmt': '%a %b %d %H:%M:%S %Y',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

# ##### SERVER CONFIGURATION ##############################
ALLOWED_HOSTS = ['arta.evolution-events.nl', 'artaxerxes.evolution-events.nl', 'registrations.evolution-events.nl']

# ##### DATABASE CONFIGURATION ############################
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': 'db.local',
        'USER': 'ee_artaxerxes',
        # From local_settings
        'PASSWORD': MYSQL_PASSWORD,
        'NAME': 'ee_artaxerxes',
    },
}

# ##### EMAIL CONFIGURATION ###############################
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'mail.local'

# ##### SECURITY CONFIGURATION ############################

# Note: Webserver guarantees only secure requests are processed and the
# (u)wsgi-protocol seems to pass on secure status automatically. The
# webserver also sets HSTS headers.
# Even so, let Django redirect to HTTPS as well, just in case the
# webserver config gets messed up.
SECURE_SSL_REDIRECT = True
# Session cookies will be marked as secure, so the browser will only
# send them over HTTPS
SESSION_COOKIE_SECURE = True

# validates passwords (very low security, but hey...)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
]

# How long a password reset link should work.
# TODO: A day is probably too long already, in Django (the upcoming) 3.1 this can be
# specified in seconds instead.
PASSWORD_RESET_TIMEOUT_DAYS = 1
