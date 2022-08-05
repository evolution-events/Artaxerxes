from datetime import datetime, timedelta, timezone

import factory

from apps.events.tests.factories import EventFactory
from apps.people.tests.factories import ArtaUserFactory

from ..models import (Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue,
                      RegistrationPriceCorrection)


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
                if isinstance(option, RegistrationFieldOption):
                    RegistrationFieldValueFactory.create(registration=obj, field=option.field, option=option)
                else:
                    (field, value) = option
                    RegistrationFieldValueFactory.create(registration=obj, field=field, value=value)


class RegistrationPriceCorrectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegistrationPriceCorrection

    price = 10
    description = factory.Sequence(lambda n: 'Correction %d' % n)
    when_cancelled = False


class RegistrationFieldFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegistrationField

    name = factory.Sequence(lambda n: 'field_%d' % n)
    title = factory.Sequence(lambda n: 'Field title %d' % n)
    field_type = RegistrationField.types.CHOICE

    @factory.lazy_attribute
    def allow_change_until(obj):
        if obj.allow_change_days is None:
            return None
        return datetime.now(timezone.utc) + timedelta(days=obj.allow_change_days)

    class Params:
        allow_change_days = None


class RegistrationFieldOptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegistrationFieldOption


class RegistrationFieldValueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RegistrationFieldValue

    @factory.post_generation
    def value(obj, create, value, **kwargs):
        if value:
            if obj.field.field_type.CHOICE and isinstance(value, RegistrationFieldOption):
                obj.option = value
            elif obj.field.field_type.IMAGE:
                obj.file_value = value
            else:
                obj.string_value = value
