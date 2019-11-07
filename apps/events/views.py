# from django.shortcuts import render
import reversion
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.people.models import Address, MedicalDetails

from .forms import FinalCheckForm, MedicalDetailForm, OptionsForm, PersonalDetailForm
from .models import Event, Registration


@login_required
def event_index_view(request):
    """ Landing page for events.

    (TODO: really needed?)
    """
    return render(request, 'events/index.html', {'user': request.user})


@login_required
def event_list_view(request):
    """ List of all events that people can register for. """
    # TODO: actually filter or select on events one can register for
    events = Event.objects.all()

    return render(request, 'events/list.html', {'user': request.user, 'events': events})


@login_required
def registration_step_personal_details(request, eventid=None):
    """ Step in registration process where user fills in personal details """

    event = get_object_or_404(Event, pk=eventid)
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
            registration = Registration.objects.create(user=request.user, event=event,
                                                       status=Registration.STATUS_PREPARATION_IN_PROGRESS)
            registration.save()
            return redirect('events:medicaldetailform', eventid=event.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        pd_form = PersonalDetailForm(instance=address)
    return render(request, 'events/editpersonaldetails.html', {
        'pd_form': pd_form,
        'event': event,
    })


@login_required
def registration_step_medical_details(request, eventid=None):
    """ Step in registration process where user fills in medical details """

    mdetails = None
    if hasattr(request.user, 'medicaldetails'):
        mdetails = request.user.medicaldetails
    event = get_object_or_404(Event, pk=eventid)
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
            return redirect('events:optionsform', eventid=event.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        md_form = MedicalDetailForm(instance=mdetails)
    return render(request, 'events/editmedicaldetails.html', {
        'md_form': md_form,
        'event': event,
    })


@login_required
def registration_step_options(request, eventid=None):
    """ Step in registration process where user chooses options """

    event = get_object_or_404(Event, pk=eventid)
    if request.method == 'POST':
        opt_form = OptionsForm(request.POST)
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
            return redirect('events:finalcheckform', eventid=event.id)
        else:
            messages.error(request, _('Please correct the error below.'), extra_tags='bg-danger')
    else:
        opt_form = OptionsForm()
    return render(request, 'events/editoptions.html', {
        'opt_form': opt_form,
        'event': event,
    })


@login_required
def registration_step_final_check(request, eventid=None):
    """ Step in registration process where user checks all information and agrees to conditions """

    event = get_object_or_404(Event, pk=eventid)
    personal_details = Address.objects.filter(user=request.user).first()  # Returns None if nothing was found
    medical_details = MedicalDetails.objects.filter(user=request.user).first()  # Returns None if nothing was found
    # TODO: get chosen event options and pass them on when rendering the page

    if request.method == 'POST':
        fc_form = FinalCheckForm(request.POST)
        if fc_form.is_valid():

            with reversion.create_revision():
                cancelled = Registration.STATUS_CANCELLED
                registration = Registration.objects.filter(user=request.user, event=event).exclude(status=cancelled)[0]
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
    return render(request, 'events/finalcheck.html', {
        'user': request.user,
        'event': event,
        'pdetails': personal_details,
        'mdetails': medical_details,
        'fc_form': fc_form,
    })
