# from django.shortcuts import render
import reversion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.generic import DetailView, View

from apps.events.models import Event
from apps.people.models import Address, MedicalDetails

from .forms import FinalCheckForm, MedicalDetailForm, PersonalDetailForm, RegistrationOptionsForm
from .models import Registration
from .services import RegistrationStatusService


class RegistrationStartView(LoginRequiredMixin, View):
    # TODO: This should be a POST request
    def get(self, request, eventid):
        event = get_object_or_404(Event, pk=eventid)
        registration, created = Registration.objects.get_or_create(
            event=event, user=request.user, defaults={'status': Registration.statuses.PREPARATION_IN_PROGRESS},
        )
        if registration.status.PREPARATION_IN_PROGRESS:
            return redirect('registrations:personaldetailform', registrationid=registration.id)
        else:
            return redirect('registrations:finalcheckform', registrationid=registration.id)


class RegistrationDetailView(DetailView):
    """ View a single Registration. """

    context_object_name = 'registration'
    model = Registration
    template_name = 'registrations/registration_detail.html'


@login_required
def registration_step_personal_details(request, registrationid=None):
    """ Step in registration process where user fills in personal details """

    registration = get_object_or_404(Registration, pk=registrationid)
    # Get a copy of the event annotated for this user
    event = Event.objects.for_user(request.user).get(pk=registration.event.pk)
    address = None
    if hasattr(request.user, 'address'):
        address = request.user.address
    if request.method == 'POST':
        pd_form = PersonalDetailForm(request.POST, instance=address)
        if pd_form.is_valid():
            with reversion.create_revision():
                address = pd_form.save(commit=False)  # We can't save yet because user needs to be set
                address.user = request.user
                address.save()
                reversion.set_user(request.user)
                reversion.set_comment(_("Personal info updated via frontend. The following "
                                      "fields changed: %(fields)s" % {'fields': ", ".join(pd_form.changed_data)}))

            # TODO: send verification e-mail for e-address after figuring out what to use
            # Make registration and set status to PREPARATION_IN_PROGRESS
            return redirect('registrations:medicaldetailform', registrationid=registration.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        pd_form = PersonalDetailForm(instance=address)
    return render(request, 'registrations/editpersonaldetails.html', {
        'pd_form': pd_form,
        'registration': registration,
        'event': event,
    })


@login_required
def registration_step_medical_details(request, registrationid=None):
    """ Step in registration process where user fills in medical details """

    mdetails = None
    if hasattr(request.user, 'medicaldetails'):
        mdetails = request.user.medicaldetails
    registration = get_object_or_404(Registration, pk=registrationid)
    # Get a copy of the event annotated for this user
    event = Event.objects.for_user(request.user).get(pk=registration.event.pk)
    if request.method == 'POST':
        md_form = MedicalDetailForm(request.POST, instance=mdetails)
        if md_form.is_valid():
            with reversion.create_revision():
                details = md_form.save(commit=False)
                details.user = request.user
                details.save()
                reversion.set_user(request.user)
                reversion.set_comment(_("Medical info updated via frontend. The following "
                                      "fields changed: %(fields)s" % {'fields': ", ".join(md_form.changed_data)}))

            return redirect('registrations:optionsform', registrationid=registration.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        md_form = MedicalDetailForm(instance=mdetails)
    return render(request, 'registrations/editmedicaldetails.html', {
        'md_form': md_form,
        'registration': registration,
        'event': event,
    })


@login_required
def registration_step_options(request, registrationid=None):
    """ Step in registration process where user chooses options """

    registration = get_object_or_404(Registration, pk=registrationid)
    # Get a copy of the event annotated for this user
    event = Event.objects.for_user(request.user).get(pk=registration.event.pk)

    if not event.registration_fields.all():
        return redirect('registrations:finalcheckform', registrationid=registration.id)

    # TODO: Check registration status?
    if request.method == 'POST':
        opt_form = RegistrationOptionsForm(registration.event, request.user, registration=registration,
                                           data=request.POST)
        if opt_form.is_valid():
            with reversion.create_revision():
                opt_form.save(registration)
                reversion.set_user(request.user)
                reversion.set_comment(_("Options updated via frontend. The following "
                                      "fields changed: %(fields)s" % {'fields': ", ".join(opt_form.changed_data)}))

            if registration.status.PREPARATION_IN_PROGRESS:
                with reversion.create_revision():
                    registration.status = Registration.statuses.PREPARATION_COMPLETE
                    registration.save()
                    reversion.set_user(request.user)
                    reversion.set_comment(_("Registration preparation finalized via frontend."))

            return redirect('registrations:finalcheckform', registrationid=registration.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        opt_form = RegistrationOptionsForm(registration.event, request.user, registration=registration)
    return render(request, 'registrations/editoptions.html', {
        'opt_form': opt_form,
        'registration': registration,
        'event': event,
    })


@login_required
def registration_step_final_check(request, registrationid=None):
    """ Step in registration process where user checks all information and agrees to conditions """

    qs = Registration.objects.with_price()
    registration = get_object_or_404(qs, pk=registrationid)
    # Get a copy of the event annotated for this user
    event = Event.objects.for_user(request.user).get(pk=registration.event.pk)
    personal_details = Address.objects.filter(user=request.user).first()  # Returns None if nothing was found
    medical_details = MedicalDetails.objects.filter(user=request.user).first()  # Returns None if nothing was found
    # TODO: Check registration status?

    if request.method == 'POST':
        fc_form = FinalCheckForm(request.POST)
        if fc_form.is_valid():
            try:
                RegistrationStatusService.finalize_registration(registration)
            except ValidationError as ex:
                messages.error(request, ex)

                # TODO: Redirect elsewhere? Or Maybe remove this except clause when status is checked above?
                return redirect('registrations:finalcheckform', registration.pk)

            # TODO: Show result
            return redirect('events:eventlist')
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        fc_form = FinalCheckForm()
    return render(request, 'registrations/finalcheck.html', {
        'user': request.user,
        'registration': registration,
        'event': event,
        'pdetails': personal_details,
        'mdetails': medical_details,
        'fc_form': fc_form,
    })
