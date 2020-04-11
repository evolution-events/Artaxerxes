import factory

from ..models import ArtaUser, EmergencyContact, MedicalDetails


class ArtaUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ArtaUser
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.Faker('email')


class MedicalDetailsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MedicalDetails
    food_allergies = factory.Faker('sentence')
    event_risks = factory.Faker('text')
    user = factory.SubFactory(ArtaUserFactory)


class EmergencyContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmergencyContact
    contact_name = factory.Faker('name')
    phone_number = factory.Faker('phone_number')
