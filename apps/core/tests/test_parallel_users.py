import contextlib
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import django.db
from django.test import Client, TransactionTestCase, skipUnlessDBFeature, tag
from django.urls import reverse
# Use factoryboy's random generator seed management
from factory.random import randgen

from apps.events.tests.factories import EventFactory
from apps.people.tests.factories import ArtaUserFactory
from apps.registrations.models import Registration
from apps.registrations.tests.factories import RegistrationFactory


class Stopwatch:
    """ Contextmanager to keep elapsed time """

    def __enter__(self):
        self.start = time.monotonic()
        self.end = None
        return self

    def __exit__(self, type, value, traceback):
        self.end = time.monotonic()

    def seconds(self):
        if self.end is not None:
            return self.end - self.start
        # If not done, return a running total
        return time.monotonic() - self.start

    def ms(self):
        return self.seconds() * 1000


# Skip for Sqlite, which does not handle locks gracefully
# https://code.djangoproject.com/ticket/29280
@skipUnlessDBFeature('test_db_allows_multiple_connections')
@tag('benchmark')
# This uses TransactionTestCase to *not* use transactions for rollback, so different threads can actually see each
# other's changes.
class TestParallelUsers(TransactionTestCase):
    duration = 10
    threads = 40
    browse_views = [
        'core:dashboard',
        'core:practical_info',
        'core:about',
        'people:index',
    ]
    finalcheck_view = 'registrations:step_final_check'

    # Cannot use setUpTestData, TransactionTestCase does not offer it
    def setUp(self):
        self.event = EventFactory(registration_opens_in_days=1, starts_in_days=1, public=True, slots=self.threads / 2)
        self.users = ArtaUserFactory.create_batch(self.threads)
        for user in self.users:
            RegistrationFactory(event=self.event, user=user, preparation_complete=True)

    def run_threads(self, func, duration=None, timeout=None, min_rps=None):
        """ Helper to run func in parallel for each user. """
        done = threading.Event()
        all_started = threading.Barrier(len(self.users) + 1)
        threads = []
        request_counts_lock = threading.Lock()
        request_counts = defaultdict(int)
        request_latencies = defaultdict(int)
        for i, user in enumerate(self.users):
            def target(i=i, user=user):
                # Run in a subtest to handle errors
                with self.subTest(user=user, index=i):
                    # Make sure the db connection is closed afterwards, Django only autocloses after a real request
                    with contextlib.closing(django.db.connection):
                        client = Client()
                        client.force_login(user)
                        all_started.wait()
                        for (view, latency) in func(client=client, user=user, index=i, done=done):
                            with request_counts_lock:
                                request_counts[view] += 1
                                request_latencies[view] += latency
            thread = threading.Thread(target=target)
            thread.start()
            threads.append(thread)

        # Wait for all threads to be initialized before starting
        # their functions and starting the duration
        all_started.wait()
        # Make sure that all threads are signalled to stop after duration
        threading.Timer(duration or timeout, lambda: done.set()).start()
        with Stopwatch() as stopwatch:
            for thread in threads:
                thread.join()
        if timeout:
            self.assertFalse(done.is_set(), msg="Test time expired before all registrations were completed")
        actual_duration = stopwatch.seconds()

        print()  # noqa: T001
        print("{} ({:.1f} seconds, {} threads)".format(self.id(), actual_duration, len(self.users)))  # noqa: T001
        for (view, count) in request_counts.items():
            latency = request_latencies[view]
            print("{:>40}: {:>4d} requests, {:>5.1f} r/s, {:>4.0f} ms".format(  # noqa: T001
                view, count, count / actual_duration, latency / count),
            )

        total_count = sum(request_counts.values())
        total_latency = sum(request_latencies.values())
        print("{:>40}: {:>4d} requests, {:>5.1f} r/s, {:>4.0f} ms".format(  # noqa: T001
            "all", total_count, total_count / actual_duration, total_latency / total_count),
        )

        # This is a bit arbitrary and machine dependent, but maybe this at least catches extra slowdowns
        if min_rps is not None:
            requests_per_second = total_count / actual_duration
            self.assertGreaterEqual(requests_per_second, min_rps, "Request handling (too?) slow")

    def test_browsing(self):
        """ Test users browsing the regular pages. """

        def thread_func(client, user, index, done):
            while not done.is_set():
                view = randgen.choice(self.browse_views)
                with Stopwatch() as stopwatch:
                    response = client.get(reverse(view))
                self.assertEqual(response.status_code, 200)
                yield (view, stopwatch.ms())

        self.run_threads(thread_func, duration=self.duration, min_rps=10)

    def test_refreshing(self):
        """ Test users refreshing the finalcheck page. """
        def thread_func(client, user, index, done):
            reg = user.registrations.get()
            while not done.is_set():
                # Refresh finalcheck most of the time, but sometimes also other pages
                if randgen.randrange(10) == 0:
                    view = randgen.choice(self.browse_views)
                    url = reverse(view)
                else:
                    view = self.finalcheck_view
                    url = reverse(view, args=(reg.pk,))

                with Stopwatch() as stopwatch:
                    response = client.get(url)
                self.assertEqual(response.status_code, 200)
                yield (view, stopwatch.ms())

        self.run_threads(thread_func, duration=self.duration, min_rps=10)

    def test_registration(self):
        """ Test users refreshing the finalcheck until registration is open, then register. """

        timeout=20
        registration_start=5
        self.event.registration_opens_at = datetime.now(timezone.utc) + timedelta(seconds=registration_start)
        self.event.save()

        def thread_func(client, user, index, done):
            reg = user.registrations.get()
            while not done.is_set():
                view = self.finalcheck_view
                url = reverse(view, args=(reg.pk,))
                with Stopwatch() as stopwatch:
                    response = client.get(url)
                self.assertEqual(response.status_code, 200)
                yield (view + ":get", stopwatch.ms())

                if response.context['event'].registration_is_open:
                    view = self.finalcheck_view
                    url = reverse(view, args=(reg.pk,))

                    with Stopwatch() as stopwatch:
                        response = client.post(url, {'agree': 1})

                    next_url = reverse('registrations:registration_confirmation', args=(reg.pk,))
                    self.assertRedirects(response, next_url)
                    yield (view + ":post", stopwatch.ms())

                    break

        self.run_threads(thread_func, timeout=timeout, min_rps=10)
        from apps.events.models import Event
        Event.objects.for_user(self.users[0]).get()

        num_registered = (Registration.objects.filter(status=Registration.statuses.REGISTERED)).count()
        num_waiting = (Registration.objects.filter(status=Registration.statuses.WAITINGLIST)).count()
        self.assertEqual(num_registered + num_waiting, len(self.users))
        self.assertEqual(num_registered, self.event.slots)
