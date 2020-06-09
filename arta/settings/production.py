# for now fetch the development settings only
from .common import *

# these persons receive error notification
ADMINS = (
    ('Webmasters', 'webmaster@evolution-events.nl'),
)
MANAGERS = ADMINS

# turn off all debugging
DEBUG = False

# You will have to determine, which hostnames should be served by Django
ALLOWED_HOSTS = []

# This replaces the "django" logger with one that is pretty much identical to the default, except:
#  - Normally stderr-logging only happens when DEBUG is True, but we want to always log to the UWSGI log (which helps
#    diagnosing startup errors and keeps logs).
#  - The log format is changed to match UWSGI.
#  - The mail_admins handler also sends out WARNING messages.
# Django also defines a "django.server" logger which we leave unchanged, since it should only be used for runserver
# (though in practice, it was seen to be *sometimes* replaced by the "django" logger below, unsure how that works
# exactly.
LOGGING = {
    'version': 1,
    # Recommended, otherwise default loggers are disabled but not removed, which can be problematic for non-propagating
    # loggers (which then stop producing output but still prevent propagation).
    'disable_existing_loggers': False,
    'filters': {
        'ignore_404': {
            '()': 'arta.common.log.Ignore404',
        },
    },
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
        'mail_admins': {
            'level': 'WARNING',
            # These are already handled by BrokenLinksEmailMiddleware
            'filters': ['ignore_404'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'mail_admins'],
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
