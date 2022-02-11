from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic.list import ListView
from django_weasyprint import WeasyTemplateResponseMixin

from apps.registrations.models import Registration
from arta.common.db import QExpr

from .models import Event


class RegisteredEventList(LoginRequiredMixin, ListView):
    """ List of all events that the current user is registered for. """

    template_name = 'events/registered_events.html'
    model = Event
    ordering = '-start_date'

    def get_queryset(self):
        return (
            super().get_queryset()
            .for_user(self.request.user, with_registration=True)
            .filter(registration_status__in=Registration.statuses.FINALIZED)
        )

    def get_context_data(self, **kwargs):
        future = []
        past = []
        for e in self.object_list:
            if e.start_date > date.today():
                future.append(e)
            else:
                past.append(e)

        future.reverse()

        kwargs['events'] = {
            'past': past,
            'future': future,
        }
        return super().get_context_data(**kwargs)


class OrganizedEventsList(LoginRequiredMixin, ListView):
    """ List of events a user has organizer access to. """

    template_name = 'events/organized_events.html'
    allow_empty = False
    model = Event
    ordering = '-start_date'

    def get_queryset(self):
        return super().get_queryset().for_organizer(self.request.user).annotate(
            num_registered=Count('registrations', filter=Q(registrations__status=Registration.statuses.REGISTERED)),
            num_waitinglist=Count('registrations', filter=Q(registrations__status=Registration.statuses.WAITINGLIST)),
            num_cancelled=Count('registrations', filter=Q(registrations__status=Registration.statuses.CANCELLED)),
            show_registration_details=QExpr(Q(end_date__gte=date.today())),
        )

    def get_context_data(self, **kwargs):
        counts = Registration.objects.values_list('status').annotate(count=Count('status'))
        kwargs['counts'] = {status.id: count for status, count in counts}
        return super().get_context_data(**kwargs)


class EventRegistrationInfoBase(LoginRequiredMixin, ListView):
    """ Base class for various views that provide info about all participants. """

    model = Registration
    ordering = ('user__first_name', 'user__last_name')

    @cached_property
    def event(self):
        return get_object_or_404(Event.objects.for_organizer(self.request.user), pk=self.kwargs['pk'])

    def get_queryset(self):
        return super().get_queryset().filter(event=self.event, status=Registration.statuses.REGISTERED)

    def get_context_data(self, **kwargs):
        kwargs['event'] = self.event
        if getattr(self, 'print_view', False):
            kwargs['print_url'] = reverse(self.print_view, args=(self.event.pk,))
        return super().get_context_data(**kwargs)


class RegistrationForms(EventRegistrationInfoBase):
    """ Registration forms, to be printed and signed. """

    template_name = 'events/printable/registration_forms.html'
    print_view = 'events:printable_registration_forms'

    def get_queryset(self):
        return (
            super().get_queryset()
            .with_payment_status()
            .select_related('event', 'user', 'user__address')
        )


class PrintableRegistrationForms(WeasyTemplateResponseMixin, RegistrationForms):
    pass


class KitchenInfo(EventRegistrationInfoBase):
    """ Info about all participants, as relevant for the kitchen crew. """

    template_name = 'events/printable/kitchen_info.html'
    print_view = 'events:printable_kitchen_info'

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related('user', 'user__medical_details')
            .filter(user__medical_details__isnull=False)
            .exclude(user__medical_details__food_allergies="")
        )


class PrintableKitchenInfo(WeasyTemplateResponseMixin, KitchenInfo):
    pass


class SafetyReference(EventRegistrationInfoBase):
    """ All safety info about all participants, to be referenced during event. """

    template_name = 'events/printable/safety_info.html'
    print_view = 'events:printable_safety_reference'

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related('user', 'user__medical_details')
            .prefetch_related('user__emergency_contacts')
        )


class PrintableSafetyReference(WeasyTemplateResponseMixin, SafetyReference):
    pass


class SafetyInfo(EventRegistrationInfoBase):
    """ Subset of safety about all participants (that have provided some), relevant before the event. """

    template_name = 'events/printable/safety_info.html'

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related('user', 'user__medical_details')
            .exclude(user__medical_details=None)
            .exclude(
                user__medical_details__food_allergies="",
                user__medical_details__event_risks="",
            )
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(omit_contacts=True, **kwargs)
