# from django.shortcuts import render
import reversion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import DetailView, View

from apps.events.models import Event
from apps.people.models import Address, MedicalDetails

from .forms import FinalCheckForm, MedicalDetailForm, PersonalDetailForm, RegistrationOptionsForm, UserDetailsForm
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
    data = request.POST or None
    ud_form = UserDetailsForm(data=data, instance=request.user, prefix="ud")
    pd_form = PersonalDetailForm(data=data, instance=address, prefix="pd")
    if request.method == 'POST':
        if pd_form.is_valid() and ud_form.is_valid():
            with reversion.create_revision():
                user = ud_form.save()
                address = pd_form.save(commit=False)  # We can't save yet because user needs to be set
                address.user = user
                address.save()
                reversion.set_user(request.user)
                fields = pd_form.changed_data + ud_form.changed_data
                reversion.set_comment(_("Personal info updated via frontend. The following "
                                      "fields changed: %(fields)s" % {'fields': ", ".join(fields)}))

            # TODO: send verification e-mail for e-address after figuring out what to use
            # Make registration and set status to PREPARATION_IN_PROGRESS
            return redirect('registrations:medicaldetailform', registrationid=registration.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    # TODO: *if* there are other active registrations, this page should probably indicate that these will also be
    # updated when this data is changed.
    return render(request, 'registrations/editpersonaldetails.html', {
        'pd_form': pd_form,
        'ud_form': ud_form,
        'registration': registration,
        'event': event,
        'cancel_url': reverse('events:eventlist'),
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
    data = request.POST or None
    md_form = MedicalDetailForm(data=data, instance=mdetails)
    if request.method == 'POST':
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
    return render(request, 'registrations/editmedicaldetails.html', {
        'md_form': md_form,
        'registration': registration,
        'event': event,
        'back_url': reverse('registrations:personaldetailform', args=(registration.id,)),
    })


@login_required
def registration_step_options(request, registrationid=None):
    """ Step in registration process where user chooses options """

    registration = get_object_or_404(Registration, pk=registrationid)
    # Get a copy of the event annotated for this user
    event = Event.objects.for_user(request.user).get(pk=registration.event.pk)

    if not event.registration_fields.all():
        return redirect('registrations:finalcheckform', registrationid=registration.id)

    data = request.POST or None
    opt_form = RegistrationOptionsForm(registration.event, request.user, registration=registration, data=data)

    # TODO: Check registration status?
    if request.method == 'POST':
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
    return render(request, 'registrations/editoptions.html', {
        'opt_form': opt_form,
        'registration': registration,
        'event': event,
        'back_url': reverse('registrations:medicaldetailform', args=(registration.id,)),
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

    data = request.POST or None
    fc_form = FinalCheckForm(data=data)
    if request.method == 'POST':
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
    return render(request, 'registrations/finalcheck.html', {
        'user': request.user,
        'registration': registration,
        'event': event,
        'pdetails': personal_details,
        'mdetails': medical_details,
        'fc_form': fc_form,
        'modify_url': reverse('registrations:personaldetailform', args=(registration.id,)),
    })
