from datetime import datetime, timezone

import factory

from apps.events.tests.factories import EventFactory
from apps.people.tests.factories import ArtaUserFactory

from ..models import Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue


class RegistrationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Registration

    # Autocreate a user or event for this registration if none was passed
    user = factory.SubFactory(ArtaUserFactory)
    event = factory.SubFactory(EventFactory)

    status = Registration.statuses.PREPARATION_IN_PROGRESS

    @factory.lazy_attribute
    def registered_at(self):
        if self.status.ACTIVE or self.status.CANCELLED:
            return datetime.now(timezone.utc)
        return None

    class Params:
        # These are just to more concisely define status
        registered = factory.Trait(status=Registration.statuses.REGISTERED)
        waiting_list = factory.Trait(status=Registration.statuses.WAITINGLIST)
        cancelled = factory.Trait(status=Registration.statuses.CANCELLED)
        preparation_in_progress = factory.Trait(status=Registration.statuses.PREPARATION_IN_PROGRESS)
        preparation_complete = factory.Trait(status=Registration.statuses.PREPARATION_COMPLETE)

    @factory.post_generation
    def options(obj, create, options, **kwargs):

        if options:
            # Cannot add options when only building, since we will not have an id yet
            assert(create)
            for option in options:
                RegistrationFieldValueFactory.create(registration=obj, field=option.field, option=option)


class RegistrationFieldFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegistrationField

    name = factory.Sequence(lambda n: 'field_%d' % n)
    title = factory.Sequence(lambda n: 'Field title %d' % n)
    field_type = RegistrationField.TYPE_CHOICE


class RegistrationFieldOptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegistrationFieldOption


class RegistrationFieldValueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegistrationFieldValue
