# from django.shortcuts import render
import reversion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.generic.base import View

from apps.events.models import Event
from apps.people.models import Address, MedicalDetails

from .forms import FinalCheckForm, MedicalDetailForm, PersonalDetailForm, RegistrationOptionsForm
from .models import Registration


class RegistrationStartView(LoginRequiredMixin, View):
    # TODO: This should be a POST request
    def get(self, request, eventid):
        event = get_object_or_404(Event, pk=eventid)
        registration, created = Registration.objects.get_or_create(
            event=event, user=request.user, defaults={'status': Registration.STATUS_PREPARATION_IN_PROGRESS},
        )

        return redirect('registrations:personaldetailform', registrationid=registration.id)


@login_required
def registration_step_personal_details(request, registrationid=None):
    """ Step in registration process where user fills in personal details """

    registration = get_object_or_404(Registration, pk=registrationid)
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
            messages.success(request, _('Your personal information was successfully updated!'),
                             extra_tags='bg-success')  # add bootstrap css class
            # TODO: send verification e-mail for e-address after figuring out what to use
            # Make registration and set status to 'in STATUS_PREPARATION_IN_PROGRESS'
            return redirect('registrations:medicaldetailform', registrationid=registration.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        pd_form = PersonalDetailForm(instance=address)
    return render(request, 'registrations/editpersonaldetails.html', {
        'pd_form': pd_form,
        'registration': registration,
    })


@login_required
def registration_step_medical_details(request, registrationid=None):
    """ Step in registration process where user fills in medical details """

    mdetails = None
    if hasattr(request.user, 'medicaldetails'):
        mdetails = request.user.medicaldetails
    registration = get_object_or_404(Registration, pk=registrationid)
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
            messages.success(request, _('Your medical information was successfully updated!'),
                             extra_tags='bg-success')  # add bootstrap css class
            return redirect('registrations:optionsform', registrationid=registration.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        md_form = MedicalDetailForm(instance=mdetails)
    return render(request, 'registrations/editmedicaldetails.html', {
        'md_form': md_form,
        'registration': registration,
    })


@login_required
def registration_step_options(request, registrationid=None):
    """ Step in registration process where user chooses options """

    registration = get_object_or_404(Registration, pk=registrationid)
    # TODO: Check registration status?
    if request.method == 'POST':
        opt_form = RegistrationOptionsForm(registration.event, request.user, data=request.POST)
        if opt_form.is_valid():
            # TODO save form and link event?, user?
            """with reversion.create_revision():
                opt_form.save()
                reversion.set_user(request.user)
                reversion.set_comment(_("Options updated via frontend. The following "
                                      "fields changed: %(fields)s" % {'fields': ", ".join(opt_form.changed_data)}))
            messages.success(request, _('Your options were successfully registered!'),
                             extra_tags='bg-success')  # add bootstrap css class
            """
            return redirect('registrations:finalcheckform', registrationid=registration.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        opt_form = RegistrationOptionsForm(registration.event, request.user)
    return render(request, 'registrations/editoptions.html', {
        'opt_form': opt_form,
        'registration': registration,
    })


@login_required
def registration_step_final_check(request, registrationid=None):
    """ Step in registration process where user checks all information and agrees to conditions """

    registration = get_object_or_404(Registration, pk=registrationid)
    personal_details = Address.objects.filter(user=request.user).first()  # Returns None if nothing was found
    medical_details = MedicalDetails.objects.filter(user=request.user).first()  # Returns None if nothing was found
    # TODO: get chosen event options and pass them on when rendering the page
    # TODO: Check registration status?

    if request.method == 'POST':
        fc_form = FinalCheckForm(request.POST)
        if fc_form.is_valid():

            with reversion.create_revision():
                registration.status = Registration.STATUS_PREPARATION_COMPLETE
                registration.save()
                reversion.set_user(request.user)
                reversion.set_comment(_("Registration preparation finalized via frontend."))
            messages.success(request, _('You have completed your preparation for registration!'),
                             extra_tags='bg-success')  # add bootstrap css class

            return redirect('events:eventlist')
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        fc_form = FinalCheckForm()
    return render(request, 'registrations/finalcheck.html', {
        'user': request.user,
        'registration': registration,
        'pdetails': personal_details,
        'mdetails': medical_details,
        'fc_form': fc_form,
    })
