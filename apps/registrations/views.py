# from django.shortcuts import render
import reversion
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, F, Q, When
from django.forms import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic.base import ContextMixin, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormView

from apps.events.models import Event
from apps.payments.models import Payment
from apps.payments.services import PaymentService, PaymentStatusService
from apps.people.models import Address, ArtaUser, EmergencyContact, MedicalDetails
from arta.common.views import CacheUsingTimestampsMixin

from .forms import (EmergencyContactFormSet, FinalCheckForm, MedicalDetailForm, PaymentForm, PersonalDetailForm,
                    RegistrationOptionsForm)
from .models import Registration, RegistrationFieldOption, RegistrationFieldValue
from .services import RegistrationNotifyService, RegistrationStatusService

REGISTRATION_STEPS = [
    {
        'title': _('Start registration'),
        'view': 'registrations:registration_start',
        'statuses': [],
        'change': False,
        'view_arg_attr': 'event_id',
    }, {
        'title': _('Edit registration'),
        'view': 'registrations:edit_start',
        'statuses': Registration.statuses.ACTIVE,
        'change': True,
        'view_arg_attr': 'event_id',
    }, {
        'title': _('Event options'),
        'view': 'registrations:step_registration_options',
        'cancel_view': 'core:dashboard',
        'statuses': Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    }, {
        'title': _('Personal details'),
        'view': 'registrations:step_personal_details',
        'statuses': Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    }, {
        'title': _('Safety information'),
        'view': 'registrations:step_medical_details',
        'statuses': Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    }, {
        'title': _('Emergency contacts'),
        'view': 'registrations:step_emergency_contacts',
        'statuses': Registration.statuses.DRAFT | Registration.statuses.ACTIVE,
    }, {
        'title': _('Final check'),
        'view': 'registrations:step_final_check',
        'statuses': [Registration.statuses.PREPARATION_COMPLETE],
        'change': False,
    }, {
        'title': _('Registered'),
        'view': 'registrations:registration_confirmation',
        'statuses': Registration.statuses.ACTIVE,
        'change': False,
    }, {
        'title': _('Done'),
        'view': 'registrations:edit_done',
        'statuses': Registration.statuses.ACTIVE,
        'change': True,
    },
]


class RegistrationStepMixinBase(ContextMixin):
    def get_queryset(self):
        # Only allow editing your own registrations
        qs = Registration.objects.filter(user=self.request.user)
        qs = qs.with_has_conflicting_registrations()
        return qs

    def get_success_url(self):
        view = self.steps[self.current_step_num + 1].get('view')

        return reverse(view, args=(self.registration.id,))

    @property
    def registration_id(self):
        return self.kwargs['pk']

    @cached_property
    def registration(self):
        return get_object_or_404(self.get_queryset(), pk=self.registration_id)

    @cached_property
    def event(self):
        return Event.objects.for_user(self.request.user).get(pk=self.registration.event_id)

    @cached_property
    def current_step_num(self):
        return self.steps.index(self.current_step)

    @cached_property
    def current_step(self):
        view = self.request.resolver_match.view_name
        for step in REGISTRATION_STEPS:
            if step['view'] == view:
                return step
        raise Exception(f"Current step ({view}) not listed in REGISTRATION_STEPS")

    @cached_property
    def is_change(self):
        # If change is not specified the registration status determines is_change
        return self.current_step.get('change', self.registration and self.registration.status.ACTIVE)

    @cached_property
    def steps(self):
        return [
            step for step in REGISTRATION_STEPS
            if step.get('change', None) in (self.is_change, None)
        ]

    def get_object(self):
        # In case our subclasses are also DetailView, prevent doing the same query twice
        return self.registration

    def check_request(self):
        """
        Called at the start of dispatch (so for all HTTP methods) to check if the registration is in the right state.

        Should return None for normal processing, or a response to bypass normal processing.

        These checks are not run when CacheUsingTimestampsMixin decides the cache is still valid, but in general
        anything that changes these checks should also cause the cache to become invalid.
        """
        if self.registration and self.registration.has_conflicting_registrations:
            return redirect('registrations:conflicting_registrations', self.registration.id)

        if self.is_change and not self.event.allow_change:
            start_view = 'registrations:edit_start'
            if self.current_step['view'] != start_view:
                return redirect(start_view, self.event.id)

        if not (
            self.is_change
            or self.event.registration_is_open
            or self.event.preregistration_is_open
            or self.event.can_preview
        ):
            raise Http404("Registration not open (anymore)")

        if (
            self.event.can_preview
            and self.current_step['view'] == 'registrations:registration_confirmation'
            and self.registration.status.DRAFT
        ):
            # Make an exception to the the normal status check for confirmation preview
            pass
        elif self.registration and self.registration.status not in self.current_step['statuses']:
            if self.registration.status.PREPARATION_IN_PROGRESS:
                view = 'registrations:step_registration_options'
            elif self.registration.status.PREPARATION_COMPLETE:
                view = 'registrations:step_final_check'
            elif self.registration.status.ACTIVE:
                view = 'registrations:registration_confirmation'
            else:
                raise Http404("Registration in invalid state")
            return redirect(view, self.registration.id)
        return None

    def dispatch(self, *args, **kwargs):
        response = self.check_request()
        if response is None:
            response = super().dispatch(*args, **kwargs)
        return response

    def get_context_data(self, **kwargs):
        if 'cancel_view' in self.current_step:
            kwargs.update({
                'back_url': reverse(self.current_step['cancel_view']),
                'back_text': _('Cancel'),
            })
        elif self.current_step_num > 0:
            kwargs.update({
                'back_url': reverse(self.steps[self.current_step_num - 1]['view'], args=(self.registration.pk,)),
                'back_text': _('Back'),
            })

        if self.registration and self.current_step_num < len(self.steps) - 1:
            kwargs.update({
                'forward_url': self.get_success_url(),
            })

        steps = [
            {
                'url':
                    reverse(step['view'], args=(getattr(self.registration, step.get('view_arg_attr', 'pk')),))
                    if self.registration and self.registration.status in step['statuses']
                    else None,
                'title': step['title'],
                'current': num == self.current_step_num,
            }
            for num, step in enumerate(self.steps)
        ]

        kwargs.update({
            'registration': self.registration,
            'event': self.event,
            'steps': steps,
            'is_change': self.is_change,
        })
        return super().get_context_data(**kwargs)


class RegistrationStepMixin(LoginRequiredMixin, CacheUsingTimestampsMixin, RegistrationStepMixinBase):
    """ This class ensures that LoginRequiredMixin runs its checks in dispatch before RegistrationStepMixinBase. """

    pass


class RegistrationStart(RegistrationStepMixin, TemplateView):
    template_name = 'registrations/registration_start.html'

    @cached_property
    def registration(self):
        try:
            return self.get_queryset().get(
                event=self.event,
                user=self.request.user,
                is_current=True,
            )
        except Registration.DoesNotExist:
            return None

    @cached_property
    def event(self):
        return get_object_or_404(Event.objects.for_user(self.request.user), pk=self.kwargs['eventid'])

    def post(self, request, eventid):
        with reversion.create_revision():
            reversion.set_user(self.request.user)
            reversion.set_comment(_("Registration started via frontend."))

            registration, created = Registration.objects.filter(is_current=True).get_or_create(
                event=self.event,
                user=request.user,
                defaults={'status': Registration.statuses.PREPARATION_IN_PROGRESS},
            )
        return redirect('registrations:step_registration_options', registration.id)


class RegistrationOptionsStep(RegistrationStepMixin, FormView):
    """ Step in registration process where user chooses options """

    template_name = 'registrations/step_registration_options.html'
    form_class = RegistrationOptionsForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'event': self.event,
            'user': self.request.user,
            'registration': self.registration,
        })
        return kwargs

    def form_valid(self, form):
        if form.has_changed():
            with reversion.create_revision():
                form.save(self.registration)
                reversion.set_user(self.request.user)
                reversion.set_comment(_("Options updated via frontend. The following "
                                      "fields changed: %(fields)s" % {'fields': ", ".join(form.changed_data)}))

        return super().form_valid(form)

    def check_request(self):
        # No fields? Just skip this step
        if not self.event.registration_fields.all():
            return redirect(self.get_success_url())
        return super().check_request()


class EditStart(RegistrationStepMixin, TemplateView):
    """ Start editing an active registration. """

    template_name = 'registrations/edit_start.html'

    @cached_property
    def registration(self):
        return get_object_or_404(
            self.get_queryset(),
            event=self.event,
            user=self.request.user,
            is_current=True,
        )

    @cached_property
    def event(self):
        return get_object_or_404(Event.objects.for_user(self.request.user), pk=self.kwargs['eventid'])


class PersonalDetailsStep(RegistrationStepMixin, FormView):
    """ Step in registration process where user fills in personal details """

    template_name = 'registrations/step_personal_details.html'
    form_class = PersonalDetailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        try:
            address = self.request.user.address
        except ArtaUser.address.RelatedObjectDoesNotExist:
            address = Address(user=self.request.user)

        kwargs.update({
            'user': self.request.user,
            'address': address,
        })
        return kwargs

    def form_valid(self, form):
        if form.has_changed():
            with reversion.create_revision():
                form.save()
                reversion.set_user(self.request.user)
                fields = form.user_form.changed_data + form.address_form.changed_data
                reversion.set_comment(_("Personal info updated via frontend. The following "
                                        "fields changed: %(fields)s" % {'fields': ", ".join(fields)}))

        return super().form_valid(form)


class MedicalDetailsStep(RegistrationStepMixin, FormView):
    """ Step in registration process where user fills in medical details """

    template_name = 'registrations/step_medical_details.html'
    form_class = MedicalDetailForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        try:
            details = self.request.user.medical_details
        except ArtaUser.medical_details.RelatedObjectDoesNotExist:
            details = MedicalDetails(user=self.request.user)

        kwargs.update({
            'instance': details,
        })
        return kwargs

    def form_valid(self, form):
        if form.has_changed():
            with reversion.create_revision():
                # Make sure a revision is generated even when MedicalDetails is deleted
                # TODO: This is a workaround, see https://github.com/etianen/django-reversion/issues/830
                reversion.add_to_revision(form.instance)
                form.save(registration=self.registration)
                reversion.set_user(self.request.user)
                reversion.set_comment(_("Medical info updated via frontend. The following "
                                      "fields changed: %(fields)s" % {'fields': ", ".join(form.changed_data)}))

        return super().form_valid(form)


class EmergencyContactsStep(RegistrationStepMixin, FormView):
    """ Step in registration process where user fills in emergency contacts """

    template_name = 'registrations/step_emergency_contacts.html'
    form_class = EmergencyContactFormSet

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        kwargs.update({
            'instance': self.request.user,
        })
        return kwargs

    def form_valid(self, form):
        if form.has_changed():
            with reversion.create_revision():
                form.save()
                reversion.set_user(self.request.user)
                reversion.set_comment(_("Emergency contacts updated via frontend."))

        if self.registration.status.PREPARATION_IN_PROGRESS:
            try:
                with reversion.create_revision():
                    RegistrationStatusService.preparation_completed(self.registration)
                    reversion.set_user(self.request.user)
                    reversion.set_comment(_("Registration preparation completed via frontend."))
            except ValidationError as ex:
                [messages.error(self.request, m) for m in ex.messages]
                return self.form_invalid(form)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        res = super().get_context_data(**kwargs)
        # FormView does not know we're using a formset, but it makes the template more readable like this
        res['formset'] = res['form']
        return res


class FinalCheck(RegistrationStepMixin, FormView):
    """ Step in registration process where user checks all information and agrees to conditions """

    template_name = 'registrations/step_final_check.html'
    form_class = FinalCheckForm

    def get_queryset(self):
        return super().get_queryset().with_price()

    def get_modify_url(self):
        # TODO: This hardcodes skipping the first "start" step, but
        # maybe we can do this more elegantly?
        return reverse(self.steps[1]['view'], args=(self.registration.pk,))

    def get_confirm_url(self):
        return reverse('registrations:registration_confirmation', args=(self.registration.pk,))

    def form_valid(self, form):
        try:
            # This intentionally does *not* create a revision for performance reasons (to make the registration request
            # as a whole, but also the transaction that has the event locked, shorter).
            RegistrationStatusService.finalize_registration(self.registration)
        except ValidationError as ex:
            [messages.error(self.request, _("Could not complete registration: {}").format(m)) for m in ex.messages]

            # Redirect to ourselves to force a clean recheck of everything (in case things changed between the start of
            # the request and finalize_registration checking them).
            return redirect('registrations:step_final_check', self.registration.id)

        # Confirm registration by e-mail
        RegistrationNotifyService.send_confirmation_email(self.request, self.registration)

        return super().form_valid(form)

    def instances_used(self):
        """ Returns all model instances used by this view, their updated_at fields are used for caching. """
        user = self.request.user
        # We need to return querysets, so can't just return request.user
        yield ArtaUser.objects.filter(pk=user.pk)
        # Include all a users registrations (technically only the current one and other REGISTERED ones, though
        # CANCELLED ones could previously have been included wheh they were still REGISTERED, so basically all of
        # them).
        yield Registration.objects.filter(user=user.pk)

        yield RegistrationFieldValue.objects.filter(registration=self.registration_id)
        # This returns RegistrationFieldOptions, which are used for their "full" status.
        yield RegistrationFieldOption.objects.filter(registrationfieldvalue__registration=self.registration_id)

        # These are reverse OneToOne on user, but accessing them through there returns objects rather than querysets
        yield Address.objects.filter(user=user.pk)
        yield MedicalDetails.objects.filter(user=user.pk)
        yield EmergencyContact.objects.filter(user=user.pk)

        # The event has a virtual updated timestamp at the moment registration opens (e.g. when registration is open
        # and the event was not updated *after* the registration opened, use
        # public_registration_opens_at/invitee_registrations_opens_at (whichever is later) instead of updated_at).
        # Calling values() without arguments clears field list and allows redefining updated_at with a different value.
        event_qs = Event.objects.filter(registrations=self.registration_id)
        yield event_qs.values().values(updated_at=Case(
            # TODO: This should check against the start date to invalidate the cache when registration closes.
            # However, casting date to datetime produces a naive timestamp at midnight, which is interpreted by Django
            # (django.db.backends.mysql.DatabaseOperations.convert_datetimefield_value) in the db connection timezone
            # (UTC by default). However, for Event.registration_is_open timezone.now is converted to a date to compare
            # against start_date, and that conversion happens in the django TIMEZONE, so this check does not match.
            # A solution could be to have a registration_closes_at timestamp instead of using the start_date.
            # When(
            #     start_date__lte=timezone.now(),
            #     start_date__gt=F('updated_at'),
            #     then=Cast(F('start_date'), output_field=DateTimeField()),
            # ),
            When(
                condition=Q(public_registration_opens_at__lte=timezone.now())
                & (
                    Q(invitee_registration_opens_at=None)
                    | Q(public_registration_opens_at__gt=F('invitee_registration_opens_at'))
                ) & Q(public_registration_opens_at__gt=F('updated_at')),
                then=F('public_registration_opens_at'),
            ),
            When(
                condition=Q(invitee_registration_opens_at__lte=timezone.now())
                & Q(invitee_registration_opens_at__gt=F('updated_at')),
                then=F('invitee_registration_opens_at'),
            ),
            default=F('updated_at'),
        ))

    def get_context_data(self, **kwargs):
        personal_details = Address.objects.filter(user=self.request.user).first()
        medical_details = MedicalDetails.objects.filter(user=self.request.user).first()
        emergency_contacts = self.request.user.emergency_contacts.all()

        options = self.registration.active_options
        if not self.registration.admit_immediately:
            # Not relevent for pending registrations
            any_is_full = False
        else:
            any_is_full = self.event.full or any(value.option.full for value in options if value.option)
        total_price = sum(o.price for o in options if o.price is not None)

        kwargs.update({
            'user': self.request.user,
            'pdetails': personal_details,
            'mdetails': medical_details,
            'emergency_contacts': emergency_contacts,
            'any_is_full': any_is_full,
            'options_by_section': RegistrationFieldValue.group_by_section(options),
            'total_price': total_price,
            'modify_url': self.get_modify_url(),
            'confirm_url': self.get_confirm_url(),
        })
        return super().get_context_data(**kwargs)


class RegistrationConfirmation(RegistrationStepMixin, DetailView):
    """ View confirmation after registration. """

    context_object_name = 'registration'
    template_name = 'registrations/registration_confirmation.html'

    def get_queryset(self):
        return super().get_queryset().with_price()


class EditDone(RegistrationStepMixin, DetailView):
    """ View confirmation after editing registration. """

    context_object_name = 'registration'
    template_name = 'registrations/edit_done.html'


class ConflictingRegistrations(LoginRequiredMixin, DetailView):
    """ Rejected registration due to conflicting registrations. """

    context_object_name = 'registration'
    template_name = 'registrations/conflicting_registrations.html'

    def get_queryset(self):
        return Registration.objects.filter(user=self.request.user).select_related('event')

    def render_to_response(self, context):
        # Check this in render_to_response, which is late enough to access self.object *and* can return a response.

        if self.object.status.ACTIVE:
            return redirect('registrations:registration_confirmation')

        conflicts = Registration.objects.conflicting_registrations_for(self.object).select_related('event')
        if not conflicts:
            # Let finalcheck sort out where to go
            return redirect('registrations:step_final_check', self.registration.id)

        conflicting_event = conflicts.first().event

        context.update({
            'conflicting_event': conflicting_event,
            'back_url': reverse('core:dashboard'),
        })

        return super().render_to_response(context)


class PaymentStatus(LoginRequiredMixin, FormView):
    """ Show the payment status of a given event. """

    template_name = 'registrations/payment_status.html'
    form_class = PaymentForm

    @cached_property
    def event(self):
        return get_object_or_404(Event.objects.for_user(self.request.user), pk=self.kwargs['pk'])

    @cached_property
    def registration(self):
        return Registration.objects.current_for(
            event=self.kwargs['pk'], user=self.request.user,
        ).with_payment_status().get()

    def get_context_data(self, **kwargs):
        options = self.registration.options.select_related('field', 'option')
        priced_options = options.exclude(option=None).exclude(option__price=None)
        price_corrections = self.registration.price_corrections.with_active().order_by('created_at')
        completed_payments = self.registration.payments.filter(status=Payment.statuses.COMPLETED).order_by('timestamp')
        custom_amount = ('custom-amount' in self.request.GET)

        kwargs.update({
            'event': self.event,
            'registration': self.registration,
            'priced_options': priced_options,
            'price_corrections': price_corrections,
            'completed_payments': completed_payments,
            'payable': self.registration.payment_status.PAYABLE or custom_amount,
            'custom_amount': custom_amount,
        })
        return super().get_context_data(**kwargs)

    def dispatch(self, *args, **kwargs):
        if (
            self.request.user.is_authenticated
            and not self.registration.status.FINALIZED
            and not self.event.can_preview
        ):
            return redirect('registrations:registration_start', self.kwargs['pk'])
        return super().dispatch(*args, **kwargs)

    def get_initial(self):
        return {
            'amount': self.registration.amount_due,
        }

    def form_valid(self, form):
        custom_amount = form.cleaned_data['amount']

        # Likely the payment was processed while this page was still open, so prevent double payments
        if not self.registration.payment_status.PAYABLE and not custom_amount:
            return redirect(self.request.path)

        amount = custom_amount if custom_amount is not None else self.registration.amount_due

        with reversion.create_revision():
            payment = Payment.objects.create(
                registration=self.registration,
                amount=amount,
            )
            next_url = reverse('registrations:payment_done', args=(payment.pk,))
            method = self.request.POST.get('method', '')
            url = PaymentService.start_payment(self.request, payment, next_url, method)

            reversion.set_user(self.request.user)
            reversion.set_comment(_("Payment via {} started via frontend ({} / {}).").format(
                method, payment.id, payment.mollie_id))

        return redirect(url)


class PaymentDone(LoginRequiredMixin, SingleObjectMixin, TemplateView):
    template_name = 'registrations/payment_done.html'
    model = Payment
    context_object_name = 'payment'

    def get(self, request, pk):
        self.object = self.get_object()
        # The webhook should have been called before the user is redirected back to here, but if still pending, update
        # just in case it failed.
        if self.object.status.PENDING:
            PaymentStatusService.update_payment_status(self.object)
        return super().get(request, pk)


class RegistrationPaymentDetails(LoginRequiredMixin, DetailView):
    """ Show the payment details of a given registration for organizers. """

    template_name = 'registrations/registration_payment_details.html'
    model = Registration
    context_object_name = 'registration'

    def get_queryset(self):
        return Registration.objects.with_payment_status().filter(event__organizer_group__user=self.request.user)

    @cached_property
    def registration(self):
        return Registration.objects.current_for(
            event=self.kwargs['pk'], user=self.request.user,
        ).with_payment_status().get()

    def get_context_data(self, **kwargs):
        registration = self.object
        options = registration.options.select_related('field', 'option')
        priced_options = options.exclude(option=None).exclude(option__price=None)
        price_corrections = registration.price_corrections.with_active().order_by('created_at')
        completed_payments = registration.payments.filter(status=Payment.statuses.COMPLETED).order_by('timestamp')

        kwargs.update({
            'priced_options': priced_options,
            'price_corrections': price_corrections,
            'completed_payments': completed_payments,
        })
        return super().get_context_data(**kwargs)
