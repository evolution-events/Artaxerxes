import os
import random
import re
import threading

from locust import HttpUser, SequentialTaskSet, between, tag, task

"""
This file allows load testing an instance. The instance should be set up as normal (possibly on another machine), then
this script (using the locust tool) will fire requests at it. There is also a preparedb.py script that should be run on
the system-under-test to make sure the right data and users are present to be used by the load testing script.

# On system-under-test and client (change the password to something different first):
export LOCUST_USER_PASSWORD=lkjasfsdafdfjafdskdsf

# On system-under-test, make sure mysql is used. When running with runserver, e.g. use something like:
export DJANGO_SETTINGS_MODULE=arta.settings.test_mysql

# On the system-under-test, prepare the db normally (e.g. migrate), then load data:
./manage.py flush
./manage.py shell -c 'import tools.locust.preparedb'

# On the client install locust: pip install locust
# Then run with e.g.
    locust  --host https://arta-staging.evolution-events.nl --users 10 --hatch-rate 10 --tags register
# And then open http://localhost:8089 to start the test
#
# Some useful shell commands to open registrations and undo the test:

from apps.registrations.models import Registration
from apps.events.models import Event
from datetime import datetime, timedelta, timezone
from django.db.models import Count
Event.objects.all().update(registration_opens_at=datetime.now(timezone.utc))
Event.objects.all().update(registration_opens_at=datetime.now(timezone.utc) + timedelta(days=1))
Registration.objects.all().update(status=Registration.statuses.PREPARATION_COMPLETE)
# Counts per registration status
Registration.objects.all().values('status').annotate(count=Count('status'))
# Users with more than one REGISTERED status
Registration.objects.all().values('user').filter(
    status=Registration.statuses.REGISTERED).annotate(count=Count('user')).filter(count__gt=1)

# The update() calls above don't work right now (See TODO in arta.common.db), so you can use these instead:
e = Event.objects.get()
e.registration_opens_at=datetime.now(timezone.utc)
e.save()
e = Event.objects.get()
e.registration_opens_at=datetime.now(timezone.utc) + timedelta(days=1)
e.save()
for r in Registration.objects.all():
    r.status=Registration.statuses.PREPARATION_COMPLETE
    r.save()
"""

# Run this many threads (locust users) per Arta user
events_per_user = 2


class ApplicationUser(HttpUser):
    wait_time = between(2, 10)
    next_user_lock = threading.Lock()
    next_user = 0
    next_event_idx = 0
    # TODO: Generate these using django's reverse?
    login_url = '/accounts/login/'
    dashboard_url = '/'
    browse_urls = [
        dashboard_url,
        '/practical_info',
        '/about_this_system',
    ]
    register_link_re = re.compile(r'href="[^"/]*(/registrations/\d+/)"')
    finalcheck_url_re = re.compile(r'/registrations/fc/\d+/$')
    conflict_url_re = re.compile(r'/registrations/cr/\d+/$')
    confirm_url_re = re.compile(r'/registrations/rc/\d+/$')
    password = os.environ['LOCUST_USER_PASSWORD']

    def on_start(self):
        cls = self.__class__
        # Locust does not seem to have any way way to assign user credentials, so just keep a counter. This breaks in
        # distributed mode.
        with cls.next_user_lock:
            self.user_id = cls.next_user
            self.event_idx = cls.next_event_idx
            cls.next_event_idx += 1
            if cls.next_event_idx == events_per_user:
                cls.next_event_idx = 0
                cls.next_user += 1

        self.login()

    def login(self):
        cls = self.__class__

        # Django requires referrer for HTTPS requests
        # https://stackoverflow.com/a/34444974/740048
        self.client.headers['Referer'] = self.client.base_url

        # Get the CSRF token from the login page
        response = self.client.get(cls.login_url)
        csrftoken = response.cookies['csrftoken']
        self.client.headers['X-CSRFToken'] = csrftoken

        # Then do the actual login
        email = 'user{}@example.com'.format(self.user_id)
        response = self.client.post(
            cls.login_url,
            {'login': email, 'password': cls.password},
            allow_redirects=False,
        )

        # Login regenerates the token, so update it for all future requests
        csrftoken = response.cookies['csrftoken']
        self.client.headers['X-CSRFToken'] = csrftoken

        assert(response.status_code == 302)
        # XXX: This breaks when installed into a subpath
        assert(response.next.path_url == self.dashboard_url)

    @task
    @tag('browse')
    def browse(self):
        url = random.choice(self.browse_urls)
        response = self.client.get(url, allow_redirects=False)
        assert(response.status_code == 200)

    @tag('register')
    @task
    class RegisterTaskSet(SequentialTaskSet):
        # Aggressive refreshing
        wait_time = between(0, 0)
        use_etag = True

        @task
        def start(self):
            """ Figure out the registration page to refresh. """
            url = self.user.dashboard_url
            response = self.client.get(url, allow_redirects=False)
            assert(response.status_code == 200)

            # Find the link to the registration start view
            matches = self.user.register_link_re.findall(response.text)

            # Abort if no link found (already registered)
            if self.user.event_idx >= len(matches):
                self.interrupt(reschedule=False)

            # TODO: This is fragile, since the events get shifted once registration completes (and if there are extra
            # events, another registration run might start).
            url = matches[self.user.event_idx]

            # Start view should redirect to the finalcheck view, which is what we'll be refreshing
            response = self.client.get(url, name="registration_start")
            assert response.status_code == 200
            # When redirected to the conflict url, we cannot register anymore either
            if self.user.conflict_url_re.search(response.url):
                self.interrupt(reschedule=False)
            assert self.user.finalcheck_url_re.search(response.url)
            self.refresh_url = response.url
            # Make sure to do at least one proper get in refresh() in case registration is already open
            self.refresh_etag = None

        @task
        def refresh(self):
            """ Keep refreshing the registration page, until a register button appears. """
            url = self.refresh_url
            headers = {}
            valid_responses = [200]

            if self.use_etag and self.refresh_etag:
                headers['If-None-Match'] = self.refresh_etag
                # Not modified
                valid_responses.append(304)

            response = self.client.get(url, name="refresh", headers=headers)
            self.refresh_etag = response.headers.get('ETag', None)

            assert(response.status_code in valid_responses)

            # Keep refreshing until a submit button appears
            submit_button = '<button class="btn btn-success" type="submit">'
            if response.status_code == 304 or submit_button not in response.text:
                self.schedule_task(self.refresh)

        @task
        def register(self):
            """ Finalize the registration. """
            url = self.refresh_url
            data = {'agree': 1}
            response = self.client.post(url, data, allow_redirects=False, name="register")
            assert(response.status_code == 302)
            assert(self.user.confirm_url_re.search(response.next.path_url)
                   or self.user.finalcheck_url_re.search(response.next.path_url)
                   or self.user.conflict_url_re.search(response.next.path_url))
