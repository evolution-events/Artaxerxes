import re
from unittest import mock, skip

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.events.models import Event
from apps.events.tests.factories import EventFactory
from apps.people.models import ArtaUser
from apps.people.tests.factories import AddressFactory, EmergencyContactFactory, GroupFactory

from ..models import Registration, RegistrationField, RegistrationFieldValue
from ..services import RegistrationStatusService
from .factories import RegistrationFactory, RegistrationFieldFactory, RegistrationFieldOptionFactory


class TestRegistrationStatusService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory(registration_opens_in_days=-1, public=True)

        cls.crew_invite_group = GroupFactory()
        cls.invite_field_group = GroupFactory()

        cls.type = RegistrationFieldFactory(event=cls.event, name="type")
        cls.player = RegistrationFieldOptionFactory(field=cls.type, title="Player")
        cls.crew = RegistrationFieldOptionFactory(field=cls.type, title="Crew")
        cls.crew_invite = RegistrationFieldOptionFactory(
            field=cls.type, title="Crew invite", invite_only=cls.crew_invite_group)

        cls.section = RegistrationFieldFactory(
            event=cls.event, name="section", depends=cls.player, field_type=RegistrationField.types.SECTION,
        )

        cls.gender = RegistrationFieldFactory(event=cls.event, name="gender", depends=cls.player)
        cls.option_m = RegistrationFieldOptionFactory(field=cls.gender, title="M", slots=2)
        cls.option_f = RegistrationFieldOptionFactory(field=cls.gender, title="F", slots=2)

        cls.origin = RegistrationFieldFactory(event=cls.event, name="origin", depends=cls.player, required=False)
        cls.option_nl = RegistrationFieldOptionFactory(field=cls.origin, title="NL", slots=2)
        cls.option_intl = RegistrationFieldOptionFactory(field=cls.origin, title="INTL", slots=2)

        cls.extra_nights = RegistrationFieldFactory(event=cls.event, name="nights")
        cls.one_night = RegistrationFieldOptionFactory(field=cls.extra_nights, title="one")
        cls.two_nights = RegistrationFieldOptionFactory(field=cls.extra_nights, title="two", depends=cls.crew)

        cls.invite = RegistrationFieldFactory(event=cls.event, name="invite", invite_only=cls.invite_field_group)
        cls.invite_opt = RegistrationFieldOptionFactory(field=cls.invite, title="invite_opt")

        cls.default_options = [cls.player, cls.option_m, cls.option_nl, cls.one_night]

    def incomplete_registration_helper(
        self, empty_field=None, with_emergency_contact=True, with_address=True, options=True,
        exception=ValidationError, inactive_options=(), group=None,
    ):
        if options is True:
            options = self.default_options
        reg = RegistrationFactory(
            event=self.event, preparation_in_progress=True, options=options, inactive_options=inactive_options,
        )

        if group:
            reg.user.groups.add(group)
            reg.user.save()

        if with_emergency_contact:
            EmergencyContactFactory(user=reg.user)
        if with_address:
            AddressFactory(user=reg.user)
        # MedicalDetails is optional, so no need to create it

        if empty_field:
            setattr(reg.user, empty_field, '')
            reg.user.save()

        if exception:
            with self.assertRaises(exception):
                RegistrationStatusService.preparation_completed(reg)
        else:
            RegistrationStatusService.preparation_completed(reg)

        reg.refresh_from_db()
        if exception:
            self.assertEqual(reg.status, Registration.statuses.PREPARATION_IN_PROGRESS)
        else:
            self.assertEqual(reg.status, Registration.statuses.PREPARATION_COMPLETE)

    def test_missing_first_name(self):
        """ Check that a missing first name prevents completing preparation """
        self.incomplete_registration_helper(empty_field='first_name')

    def test_missing_last_name(self):
        """ Check that a missing last name prevents completing preparation """
        self.incomplete_registration_helper(empty_field='last_name')

    def test_missing_address(self):
        """ Check that a missing address prevents completing preparation """
        self.incomplete_registration_helper(with_address=False)

    def test_missing_emergency_contacts(self):
        """ Check that a missing emergency contacts prevent completing preparation """
        self.incomplete_registration_helper(with_emergency_contact=False)

    def test_missing_options(self):
        """ Check that missing options prevent completing preparation """
        self.incomplete_registration_helper(options=[])

    def test_partial_options(self):
        """ Check that incomplete options prevent completing preparation """
        self.incomplete_registration_helper(options=[self.player])

    def test_partial_with_inactive_options(self):
        """ Check that an inactive option does not fulfill a required option """
        self.incomplete_registration_helper(
            options=[self.player, self.option_nl, self.one_night], inactive_options=[self.option_f])

    def test_unsatisfied_dependency_field_missing(self):
        """ Check that a omitting a field with missing dependency does not prevent completing preparation """
        self.incomplete_registration_helper(options=[self.crew, self.one_night], exception=None)

    def test_inactive_dependency_field(self):
        """ Check that an inactive option does not satisfy a dependency """
        self.incomplete_registration_helper(
            inactive_options=[self.player], options=[self.crew, self.one_night], exception=None)

    def test_unsatisfied_dependency_option(self):
        """ Check that a selecting an option whose dependency is not satisfied prevents completing preparation """
        self.incomplete_registration_helper(options=[self.player, self.option_f, self.option_nl, self.two_nights])

    def test_satisfied_dependency_option(self):
        """ Check that a selecting an option whose dependency is satisfied does not prevent completing preparation """
        self.incomplete_registration_helper(options=[self.crew, self.two_nights], exception=None)

    def test_satisfied_invite_option(self):
        """ Check that an option with satisfied invite does not prevent completion when it is present """
        self.incomplete_registration_helper(
            options=[self.crew_invite, self.one_night], exception=None, group=self.crew_invite_group)

    def test_unsatisfied_invite_option_missing(self):
        """ Check that an option with unsatisfied invite prevents completion when it is chosen """
        self.incomplete_registration_helper(options=[self.crew_invite, self.one_night])

    def test_satisfied_invite_field(self):
        """ Check that a field with satisfied invite does not prevent completion when it is present """
        self.incomplete_registration_helper(
            options=[self.crew, self.invite_opt, self.one_night], group=self.invite_field_group, exception=None)

    def test_satisfied_invite_field_missing(self):
        """ Check that a field with satisfied invite does prevent completion when it is missing """
        self.incomplete_registration_helper(options=[self.crew, self.one_night], group=self.invite_field_group)

    def test_unsatisfied_invite_field_missing(self):
        """ Check that a field with unsatisfied invite does not prevent completion when it is missing """
        self.incomplete_registration_helper(options=[self.crew, self.one_night], exception=None)

    def test_complete(self):
        """ Check that a complete registration can be completed """
        self.incomplete_registration_helper(exception=None)

    def test_required_value(self):
        """ Check accepted values for a required field. """

        CHECKED = RegistrationFieldValue.CHECKBOX_VALUES[True]
        UNCHECKED = RegistrationFieldValue.CHECKBOX_VALUES[False]

        for field_type in RegistrationField.types.constants:
            if field_type == RegistrationField.types.SECTION:
                continue

            with self.subTest(field_type=field_type):
                field = RegistrationFieldFactory(event=self.event, name="extra_field", field_type=field_type)

                with self.subTest("Missing value is not ok"):
                    self.incomplete_registration_helper()

                with self.subTest("Empty is not ok"):
                    self.incomplete_registration_helper(options=self.default_options + [(field, "")])

                if field.field_type.CHECKBOX or field.field_type.UNCHECKBOX:
                    with self.subTest("Arbitrary non-zero value is not ok"):
                        self.incomplete_registration_helper(options=self.default_options + [(field, "123")])

                    with self.subTest("Unchecked is not ok"):
                        self.incomplete_registration_helper(options=self.default_options + [(field, UNCHECKED)])

                    with self.subTest("Checked is ok"):
                        self.incomplete_registration_helper(
                            options=self.default_options + [(field, CHECKED)],
                            exception=None,
                        )
                elif field.field_type.CHOICE:
                    option = RegistrationFieldOptionFactory(field=field, title="Foo")
                    with self.subTest("Option is ok"):
                        self.incomplete_registration_helper(
                            options=self.default_options + [(field, option)],
                            exception=None,
                        )
                else:
                    with self.subTest("Arbitrary non-empty value is ok"):
                        self.incomplete_registration_helper(
                            options=self.default_options + [(field, "123")],
                            exception=None,
                        )

                field.delete()

    def test_optional_value(self):
        """ Check accepted values for a non-required field. """

        CHECKED = RegistrationFieldValue.CHECKBOX_VALUES[True]
        UNCHECKED = RegistrationFieldValue.CHECKBOX_VALUES[False]

        for field_type in RegistrationField.types.constants:
            if field_type == RegistrationField.types.SECTION:
                continue

            with self.subTest(field_type=field_type):
                field = RegistrationFieldFactory(
                    event=self.event, name="extra_field", field_type=field_type, required=False,
                )

                with self.subTest("Missing value is ok"):
                    self.incomplete_registration_helper(exception=None)

                if field.field_type.CHECKBOX or field.field_type.UNCHECKBOX:
                    with self.subTest("Arbitrary non-zero value is not ok"):
                        self.incomplete_registration_helper(options=self.default_options + [(field, "123")])

                    with self.subTest("Unchecked is ok"):
                        self.incomplete_registration_helper(
                            options=self.default_options + [(field, UNCHECKED)],
                            exception=None,
                        )

                    with self.subTest("Checked is ok"):
                        self.incomplete_registration_helper(
                            options=self.default_options + [(field, CHECKED)],
                            exception=None,
                        )
                else:
                    with self.subTest("Empty is ok"):
                        self.incomplete_registration_helper(
                            options=self.default_options + [(field, "")],
                            exception=None,
                        )

                    if field.field_type.CHOICE:
                        option = RegistrationFieldOptionFactory(field=field, title="Foo")
                        with self.subTest("Option is ok"):
                            self.incomplete_registration_helper(
                                options=self.default_options + [(field, option)],
                                exception=None,
                            )
                    else:
                        with self.subTest("Arbitrary non-empty value is ok"):
                            self.incomplete_registration_helper(
                                options=self.default_options + [(field, "123")],
                                exception=None,
                            )

                field.delete()

    def test_register_until_option_full(self):
        """ Register until the option slots are taken and the next registration ends up on the waiting list. """
        e = self.event

        for _i in range(2):
            reg = RegistrationFactory(
                event=e, preparation_complete=True,
                options=self.default_options,
            )
            RegistrationStatusService.finalize_registration(reg)
            self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            options=self.default_options,
        )
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.WAITINGLIST)

    def test_register_until_event_full(self):
        """ Register until the event slots are taken and the next registration ends up on the waiting list. """
        e = self.event
        e.refresh_from_db()
        e.slots = 3
        e.save()

        for _i in range(2):
            reg = RegistrationFactory(
                event=e, preparation_complete=True,
                options=[self.player, self.option_m, self.option_nl],
            )
            RegistrationStatusService.finalize_registration(reg)
            self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        # Two more registrations with different options to prevent triggering option slot limits
        reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_f, self.option_intl])
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_f, self.option_intl])
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.WAITINGLIST)

    def test_register_twice_race_condition(self):
        """ Finalize *the same* registration twice with specific timing, regression test. """
        e = self.event
        e.refresh_from_db()
        e.slots = 1
        e.save()

        reg = RegistrationFactory(event=e, preparation_complete=True, options=[self.option_f, self.option_intl])
        reg_clone = Registration.objects.get(pk=reg.pk)

        now = timezone.now()

        # Finalize the registration just before finalize_registration enters the transaction. This should *not* run
        # inside the services' transaction, after the lock, since that would deadlock (that would need threading and
        # more coordination (that would need threading and more coordination).
        # TODO: Can we write this more concise?
        def before_transaction(*args, **kwargs):
            reg_clone.status = Registration.statuses.REGISTERED
            reg_clone.registered_at = now
            reg_clone.save()

            # Let the original function also run
            return mock.DEFAULT

        with mock.patch(
            'django.db.transaction.atomic',
            side_effect=before_transaction,
            wraps=transaction.atomic,
        ):
            with self.subTest("Should raise validationError"):
                with self.assertRaises(ValidationError):
                    RegistrationStatusService.finalize_registration(reg)

        reg.refresh_from_db()
        with self.subTest("Should not change status"):
            self.assertEqual(reg.status, Registration.statuses.REGISTERED)

        with self.subTest("Should not change timestamp"):
            self.assertEqual(reg.registered_at, now)

    @skip("Conflict check disabled until improved")
    def test_register_two_events(self):
        """ Check that you can only register for one event. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration
        reg = RegistrationFactory(event=e, registered=True)

        # Causes second registration to be refused
        reg2 = RegistrationFactory(user=reg.user, event=e2, preparation_complete=True)
        with self.subTest("Should refuse registration"):
            with self.assertRaises(ValidationError):
                RegistrationStatusService.finalize_registration(reg2)
        with self.subTest("Should not change status"):
            self.assertTrue(reg2.status.PREPARATION_COMPLETE)

    def test_register_second_after_waitinglist(self):
        """ Check that you can still register for a second event after a waitinglist registration. """
        e = self.event
        e2 = EventFactory(registration_opens_in_days=-1, public=True)

        # Existing registration on the waitinglist
        reg = RegistrationFactory(event=e, waiting_list=True)

        # Does not prevent another registration
        reg2 = RegistrationFactory(user=reg.user, event=e2, preparation_complete=True)
        RegistrationStatusService.finalize_registration(reg2)
        self.assertTrue(reg2.status.REGISTERED)

    def test_event_admit_immediately_false(self):
        """ Check that admit_immediately=False on an event produces a pending registration, regardless of slots """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.slots = 3
        e.save()

        for _i in range(4):
            reg = RegistrationFactory(
                event=e, preparation_complete=True,
                options=[self.player, self.option_m, self.option_nl],
            )

            RegistrationStatusService.finalize_registration(reg)
            self.assertEqual(reg.status, Registration.statuses.PENDING)

    def test_option_admit_immediately_true(self):
        """ Check that admit_immediately=True on a selected option has precedence over the event """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.slots = 3
        e.save()

        self.crew.refresh_from_db()
        self.crew.admit_immediately = True
        self.crew.save()

        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            options=[self.crew, self.option_m, self.option_nl],
        )

        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

    def test_other_option_admit_immediately_true(self):
        """ Check that admit_immediately=True on a non-selected option has no precedence over the event """
        e = self.event
        e.refresh_from_db()
        e.admit_immediately = False
        e.slots = 3
        e.save()

        self.crew.refresh_from_db()
        self.crew.admit_immediately = True
        self.crew.save()

        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            options=[self.player, self.option_m, self.option_nl],
        )

        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.PENDING)

    def test_inactive_options_other_registration(self):
        """ Check that inactive options on other registrations do not take up slots """
        e = self.event

        for _i in range(2):
            reg = RegistrationFactory(
                event=e, registered=True,
                options=[self.player, self.option_m, self.option_nl],
            )
            for o in reg.options.all():
                o.active = None
                o.save()

        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            options=[self.player, self.option_m, self.option_nl],
        )
        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

    def test_inactive_options_own_registration(self):
        """ Check that inactive options on this registration do not take up slots """
        # This should not normally occur (inactive options are only created on active registrations), but check anyway
        # to be sure.
        e = self.event

        for _i in range(2):
            reg = RegistrationFactory(
                event=e, registered=True,
                options=[self.player, self.option_m, self.option_nl],
            )

        # Simulate change from full to non-full option
        reg = RegistrationFactory(
            event=e, preparation_complete=True,
            inactive_options=[self.option_nl],
            options=[self.player, self.option_f, self.option_intl],
        )

        RegistrationStatusService.finalize_registration(reg)
        self.assertEqual(reg.status, Registration.statuses.REGISTERED)

    @skipUnlessDBFeature('has_select_for_update')
    def test_finalize_locks(self):
        reg = RegistrationFactory(
            event=self.event, preparation_complete=True,
            options=[self.player, self.option_m, self.option_nl],
        )
        with CaptureQueriesContext(connection) as queries:
            RegistrationStatusService.finalize_registration(reg)
        with self.subTest("Must use SAVEPOINT"):
            # This ensures a transaction is started
            self.assertRegex(queries[0]["sql"], "^SAVEPOINT ")
        with self.subTest("Must lock event"):
            # This ensures that FOR UPDATE is used and that *only* the event is locked (i.e. no joins)
            match = ' FROM {table} WHERE {table}.{id_field} = {id} FOR UPDATE$'.format(
                table=re.escape(connection.ops.quote_name(Event._meta.db_table)),
                id_field=re.escape(connection.ops.quote_name(Event._meta.pk.column)),
                id=self.event.id,
            )
            self.assertRegex(queries[1]["sql"], match)
        with self.subTest("Must lock user"):
            # This ensures that FOR UPDATE is used and that *only* the event is locked (i.e. no joins)
            match = ' FROM {table} WHERE {table}.{id_field} = {id} ORDER BY .* FOR UPDATE$'.format(
                table=re.escape(connection.ops.quote_name(ArtaUser._meta.db_table)),
                id_field=re.escape(connection.ops.quote_name(ArtaUser._meta.pk.column)),
                id=reg.user.id,
            )
            self.assertRegex(queries[2]["sql"], match)
