import factory
from django.contrib.auth.models import Group, Permission

from ..models import Address, ArtaUser, EmergencyContact, MedicalDetails


class ArtaUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ArtaUser
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.Faker('email')

    @factory.post_generation
    def permissions(self, create, value, **kwargs):
        assert(create)  # Need id

        if value is not None:
            for perm in value:
                app_label, codename = perm.split('.')
                # No need to match content_type model, since that is duplicated in the codename
                permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                self.user_permissions.add(permission)


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


class AddressFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Address

    phone_number = factory.Faker('phone_number')
    address = factory.Faker('address')
    postalcode = factory.Faker('postalcode')
    city = factory.Faker('city')
    country = factory.Faker('country')

    class Params:
        minimal = factory.Trait(
            address='',
            postalcode='',
            city='',
            country='',
        )


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group

    name = factory.Faker('name')

    @factory.post_generation
    def users(self, create, value, **kwargs):
        assert(create)  # Need id

        if value is not None:
            for user in value:
                self.user_set.add(user)
