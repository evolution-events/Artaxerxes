from datetime import date, datetime, timedelta, timezone

import factory

from ..models import Event, Series


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    class Params:
        starts_in_days = 1
        duration_days = 3
        registration_opens_in_days = None
        registration_closes_in_days = None

    name = factory.Sequence(lambda n: 'Event %d' % n)
    title = "Title of event"
    description = "Description of event"
    start_date = factory.LazyAttribute(lambda obj: date.today() + timedelta(days=obj.starts_in_days))
    end_date = factory.LazyAttribute(lambda obj: obj.start_date + timedelta(days=obj.duration_days))
    email = factory.Faker('email')
    url = "http://eventname.evolution-events.nl"

    @factory.lazy_attribute
    def registration_opens_at(obj):
        if obj.registration_opens_in_days is None:
            return None
        return datetime.now(timezone.utc) + timedelta(days=obj.registration_opens_in_days)

    @factory.lazy_attribute
    def registration_closes_at(obj):
        if obj.registration_closes_in_days is None:
            return None
        return datetime.now(timezone.utc) + timedelta(days=obj.registration_closes_in_days)


class SeriesFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Series
