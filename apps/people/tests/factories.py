import factory

from ..models import ArtaUser


class ArtaUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ArtaUser
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.Faker('email')
