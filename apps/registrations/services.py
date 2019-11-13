from django.db import transaction
from django.db.models import Q
from django.forms import ValidationError
from django.utils.translation import gettext as _

from apps.events.models import Event

from .models import Registration, RegistrationFieldOption


class RegistrationStatusService:
    @staticmethod
    def finalize_registration(registration):
        """
        Finalizes a registration by setting its status to REGISTERED and doing additional needed bookkeeping.

        Current status must be PREPARATION_COMPLETE, otherwise a ValidationError is raised.

        When there are sufficient slots available for the options selected by this registration, the status is set to
        REGISTERED. If not, status is changed to STATUS_WAITINGLIST.
        """
        if not registration.status.PREPARATION_COMPLETE:
            raise ValidationError(_("Registration not ready for finalization"))

        with transaction.atomic():
            # Lock the event, to prevent multiple registrations from taking up the same slots
            Event.objects.select_for_update().get(pk=registration.event.pk)
            # This selects all options that are associated with the current registration and that have non-null slots.
            # annotated with the number of slots used.
            # TODO: This produces a fairly complex query, which should be checked for performance
            # (it must be fast, since this is the critical section for registrations)
            options_with_slots = RegistrationFieldOption.objects.with_used_slots().filter(
                Q(registrationfieldvalue__registration=registration) & ~Q(slots=None),
            )

            if any(o.full or o.used_slots >= o.slots for o in options_with_slots):
                registration.status = Registration.statuses.WAITINGLIST
            else:
                registration.status = Registration.statuses.REGISTERED

                # Set full for any options where we used the last slot
                for o in options_with_slots:
                    if o.slots - o.used_slots == 1:
                        o.full = True
                        o.save()

            registration.save()
