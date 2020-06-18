import os
import sys

from allauth.account.models import EmailAddress

from apps.events.tests.factories import EventFactory
from apps.people.models import ArtaUser
from apps.people.tests.factories import AddressFactory, EmergencyContactFactory, MedicalDetailsFactory
from apps.registrations.tests.factories import (RegistrationFactory, RegistrationFieldFactory,
                                                RegistrationFieldOptionFactory)

if not os.environ.get('LOCUST_USER_PASSWORD', False):
    sys.stderr.write("Need LOCUST_USER_PASSWORD in evironment to do anything, aborting.\n")
    sys.exit(1)

num_events = 2
num_users = 250
slots = 25
password = os.environ.get("LOCUST_USER_PASSWORD")


def create_user(email, admin=False):
    """ Create a user along with some data. """
    user = ArtaUser(email=email)
    if admin:
        user.is_superuser = True
        user.is_staff = True
    user.set_password(password)
    user.save()

    # Create a verified EmailAddress instance too
    address = EmailAddress(
        user=user,
        email=email,
        primary=True,
        verified=True,
    )
    address.save()

    AddressFactory(user=user)
    EmergencyContactFactory(user=user)
    MedicalDetailsFactory(user=user)

    return user


sys.stdout.write("Creating events...\n")
events = EventFactory.create_batch(
    num_events, registration_opens_in_days=100,
    starts_in_days=100, public=True, slots=slots,
)

event_options = []
for event in events:
    typeopt = RegistrationFieldFactory(event=event, name="type")
    player = RegistrationFieldOptionFactory(field=typeopt, title="Player")
    crew = RegistrationFieldOptionFactory(field=typeopt, title="Crew")

    gender = RegistrationFieldFactory(event=event, name="gender")
    option_m = RegistrationFieldOptionFactory(field=gender, title="M")
    option_f = RegistrationFieldOptionFactory(field=gender, title="F")

    origin = RegistrationFieldFactory(event=event, name="origin")
    option_nl = RegistrationFieldOptionFactory(field=origin, title="NL")
    option_intl = RegistrationFieldOptionFactory(field=origin, title="INTL")

    event_options.append((player, option_m, option_nl))

sys.stdout.write("Creating admin user...\n")
email = "admin@example.com"
create_user(email, admin=True)

for i in range(num_users):
    sys.stdout.write("\rCreating users... {}/{}".format(i + 1, num_users))
    sys.stdout.flush()

    email = "user{}@example.com".format(i)
    user = create_user(email)

    # And preparation completed registrations
    for event, options in zip(events, event_options):
        RegistrationFactory(event=event, user=user, preparation_complete=True, options=options)

sys.stdout.write("\n")

sys.stdout.write("Done\n")
