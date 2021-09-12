import re
from datetime import datetime, timezone

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.forms import ValidationError
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.events.models import Event
from apps.people.models import ArtaUser, EmergencyContact

from .models import Registration, RegistrationField, RegistrationFieldOption, RegistrationFieldValue


class RegistrationStatusService:
    @staticmethod
    def preparation_completed(registration):
        """
        Marks a registration as PREPARATION_COMPLETE.

        When status is already PREPARATION_COMPLETE, nothing happens. Otherwise, status must be
        PREPARATION_IN_PROGRESS, otherwise a ValidationError is raised.
        """
        if registration.status.PREPARATION_COMPLETE:
            return
        if not registration.status.PREPARATION_IN_PROGRESS:
            raise ValidationError(_("Registration no longer in progress"))

        user = registration.user

        if not hasattr(user, 'address'):
            raise ValidationError(_("Address incomplete"))

        if user.emergency_contacts.count() < EmergencyContact.MIN_PER_USER:
            raise ValidationError(_("Not enough emergency contacts"))

        if not user.first_name or not user.last_name:
            raise ValidationError(_("Name (partially) empty"))

        # Check that all fields have a value (taking dependencies into account)
        # TODO: Should this code live somewhere else?
        # TODO: How about fields where all options do not have their dependencies fulfilled? Should those be omitted?
        selected_options = RegistrationFieldOption.objects.filter(
            registrationfieldvalue__registration=registration,
        )
        all_fields = RegistrationField.objects.filter(
            event=registration.event_id,
        ).exclude(
            field_type=RegistrationField.types.SECTION,
        )
        required_fields = all_fields.filter(
            Q(depends=None) | Q(depends__in=selected_options),
        )
        # TODO: In Django 3.0, the annotation can be removed and you can pass Exists directly to exclude
        missing_fields = required_fields.annotate(
            value_exists=Exists(RegistrationFieldValue.objects.with_satisfies_required().filter(
                registration=registration,
                field=OuterRef('pk'),
                satisfies_required=True,
            )),
        ).exclude(value_exists=True)
        if missing_fields.exists():
            raise ValidationError(_("Missing registration options"))

        registration.status = Registration.statuses.PREPARATION_COMPLETE
        registration.save()

    @staticmethod
    def finalize_registration(registration):
        """
        Finalizes a registration by setting its status and doing additional needed bookkeeping.

        Current status must be PREPARATION_COMPLETE, otherwise a ValidationError is raised.

        When this registration needs to admitted later (e.g. lottery or other selection mechanism), the status becomes
        PENDING (indepenent of slots). Otherwhise, when there are sufficient slots available for the options selected
        by this registration, the status is set to REGISTERED. If there insufficient slots, the status is changed to
        WAITINGLIST.
        """
        with transaction.atomic():
            # Lock the event, to prevent multiple registrations from taking up the same slots.
            # This locks the event separately first and uses used_slots_for() rather than with_used_slots() in a single
            # query, to prevent locking any other rows than the event itself.
            # Not strictly needed for pending registrations, but does not hurt (much) either
            event = Event.objects.select_for_update().for_user(registration.user_id).get(pk=registration.event_id)

            # Lock the user, to prevent mutually exclusive registrations for the same user.
            # We do not actually need the values, so just evaluate the query and check it returns one user for good
            # meausure. We can't use .get(), since that always returns an object (wasteful) and it seems using the
            # queryset count() method does not respect select_for_update.
            if len(ArtaUser.objects.select_for_update().filter(pk=registration.user_id).values('id')) != 1:
                raise RuntimeError("User does not exist?")
            event.used_slots = Event.objects.used_slots_for(event)

            if not event.registration_is_open:
                raise ValidationError(_("Registration is not open"))

            # Refresh after taking the lock (if any)
            registration.refresh_from_db()
            if not registration.status.PREPARATION_COMPLETE:
                raise ValidationError(_("Registration not ready for finalization"))

            conflicts = Registration.objects.conflicting_registrations_for(registration).select_related('event')
            if conflicts:
                raise ValidationError(_("Already registered for {}".format(conflicts.first().event)))

            if not registration.admit_immediately:
                # Pending registrations are super-easy, just set the status, no need to look at the slots
                registration.status = Registration.statuses.PENDING
            else:
                # This selects all options that are associated with the current registration and that have non-null
                # slots. annotated with the number of slots used.
                options_with_slots = RegistrationFieldOption.objects.with_used_slots().filter(
                    Q(registrationfieldvalue__registration=registration) & ~Q(slots=None),
                )

                # If the event has slots defined, we can treat it just like any option with slots
                if event.slots is not None:
                    options_with_slots = [*options_with_slots, event]

                if any(o.full or o.used_slots >= o.slots for o in options_with_slots):
                    registration.status = Registration.statuses.WAITINGLIST
                else:
                    registration.status = Registration.statuses.REGISTERED

                    # Set full for any options (or the event as a whole) where we used the last slot
                    for o in options_with_slots:
                        if o.slots - o.used_slots == 1:
                            o.full = True
                            o.save()

            registration.registered_at = datetime.now(timezone.utc)
            registration.save()


class RegistrationNotifyService:
    @staticmethod
    def send_confirmation_email(request, registration):
        options = registration.options.select_related('field', 'option')
        # Use request.user when possible, since that will already have been loaded.
        user = request.user
        if user.pk != registration.user_id:
            user = registration.user
        context = {
            'user': user,
            'registration': registration,
            'options': options,
            'house_rules_url': request.build_absolute_uri(reverse('core:house_rules')),
        }
        body = render_to_string('registrations/email/registration_confirmation.txt', context)
        subject = render_to_string('registrations/email/registration_confirmation_subject.txt', context).strip()
        subject = settings.EMAIL_SUBJECT_PREFIX + subject
        # Remove all empty lines, except for the ones that contain just a . (then just remove the .). This allows
        # removing the empty lines produced by template tags that got removed, while keeping the empty lines that were
        # explicitly added in the template.
        body = re.sub("^\n+", "", body)
        body = re.sub("\n\n+", "\n", body)
        body = re.sub("\n\\.\n", "\n\n", body)

        email = EmailMessage(
            body=body, subject=subject, to=[user.email],
            bcc=settings.BCC_EMAIL_TO,
        )
        email.send()
