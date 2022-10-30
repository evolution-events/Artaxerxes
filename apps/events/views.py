from datetime import date, datetime

import import_export.formats.base_formats
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery, Value
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import escape
from django.views.generic.list import ListView
from django_weasyprint import WeasyTemplateResponseMixin
from reversion.models import Revision, Version

from apps.payments.admin import EventPaymentsResource
from apps.people.models import ArtaUser
from apps.registrations.models import Registration, RegistrationFieldValue
from arta.common.admin import MonetaryResourceWidget
from arta.common.db import GroupConcat, QExpr

from .admin import EventRegistrationsResource
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
            if e.in_the_past:
                past.append(e)
            else:
                future.append(e)

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
            .prefetch_related(Prefetch(
                'options', to_attr='kitchen_options',
                queryset=RegistrationFieldValue.objects
                .filter(field__is_kitchen_info=True, active=True)
                .select_related('field', 'option')))
            .filter(
                (Q(user__medical_details__isnull=False) & ~Q(user__medical_details__food_allergies=""))
                | Q(options__field__is_kitchen_info=True, options__active=True),
            ).distinct()
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


class PaymentDetailsLinkWidget(MonetaryResourceWidget):
    def render(self, value, obj):
        rendered = super().render(value, obj)
        url = reverse('registrations:registration_payment_details', args=(obj.pk,))
        return '<a href="{}">{}</a>'.format(escape(url), escape(rendered))


class RegistrationsTable(EventRegistrationInfoBase):
    """ Show a table of active registrations """

    template_name = 'events/registrations_table.html'

    def get_resource(self):
        resource = EventRegistrationsResource(self.event)
        resource.fields['price'].widget = PaymentDetailsLinkWidget()
        resource.fields['paid'].widget = PaymentDetailsLinkWidget()
        return resource

    @cached_property
    def data(self):
        resource = self.get_resource()
        return resource.export(
            resource.get_queryset()
            .filter(status__in=Registration.statuses.FINALIZED)
            .order_by('status', 'registered_at'))

    def get_context_data(self, **kwargs):
        kwargs['data'] = self.data
        kwargs['download_url'] = reverse('events:registrations_table_download', args=(self.event.pk,))

        return super().get_context_data(**kwargs)


class RegistrationsTableDownload(RegistrationsTable):
    """ Download a spreadsheet of registered registrations  """

    def get_resource(self):
        resource = super().get_resource()
        # XXX: This is a bit of a hack, but import_export does not offer enough context to widgets to distinguish
        # between viewing and exporting data...
        resource.fields['price'].widget = import_export.widgets.DecimalWidget()
        resource.fields['paid'].widget = import_export.widgets.DecimalWidget()
        return resource

    def get(self, *args, **kwargs):
        # TODO: Switch back to ODS once this is fixed: https://github.com/jazzband/tablib/issues/527
        file_format = import_export.formats.base_formats.XLSX()
        export_data = file_format.export_data(self.data)
        response = HttpResponse(export_data, content_type=file_format.get_content_type())
        response['Content-Disposition'] = 'attachment; filename="{}-{}.{}"'.format(
            self.event.name, datetime.now().strftime('%Y-%m-%d'), file_format.get_extension(),
        )
        return response


class PaymentsTable(EventRegistrationInfoBase):
    """ Show a table of payments """

    template_name = 'events/payments_table.html'

    def get_resource(self):
        return EventPaymentsResource(self.event)

    @cached_property
    def data(self):
        resource = self.get_resource()
        return resource.export(
            resource.get_queryset()
            .order_by('timestamp'))

    def get_context_data(self, **kwargs):
        kwargs['data'] = self.data
        kwargs['download_url'] = reverse('events:payments_table_download', args=(self.event.pk,))

        return super().get_context_data(**kwargs)


class PaymentsTableDownload(PaymentsTable):
    """ Download a spreadsheet of payments """

    def get_resource(self):
        resource = super().get_resource()
        # XXX: This is a bit of a hack, but import_export does not offer enough context to widgets to distinguish
        # between viewing and exporting data...
        resource.fields['amount'].widget = import_export.widgets.DecimalWidget()
        return resource

    def get(self, *args, **kwargs):
        # TODO: Switch back to ODS once this is fixed: https://github.com/jazzband/tablib/issues/527
        file_format = import_export.formats.base_formats.XLSX()
        export_data = file_format.export_data(self.data)
        response = HttpResponse(export_data, content_type=file_format.get_content_type())
        response['Content-Disposition'] = 'attachment; filename="{}-{}.{}"'.format(
            self.event.name, datetime.now().strftime('%Y-%m-%d'), file_format.get_extension(),
        )
        return response


class EventRegistrationsHistory(EventRegistrationInfoBase):
    """ History about changes to registrations for a given event. """

    template_name = 'events/event_registrations_history.html'
    paginate_by = 25

    def get_queryset(self):
        # This replaces the event queryset from our super with a revision queryset, but ListView does not seem to care
        registrations = super().get_queryset()
        users = ArtaUser.objects.filter(registrations__in=registrations)

        # This gets all revisions that are associated with the current event (via registration or user), and then
        # annotates them with the name of the user for which the edit was done (by looking up the user included in ther
        # revision directly, or through the registration included in the revision).
        revisions = Revision.objects.filter(
            Q(
                version__content_type=ContentType.objects.get_for_model(Registration),
                version__object_id__in=registrations,
            ) | Q(
                version__content_type=ContentType.objects.get_for_model(ArtaUser),
                version__object_id__in=users,
            ),
        ).distinct().annotate(
            # This quite a horrible stack of subqueries that is hopefully more performant than a ton of separate
            # queries that seems to have been the alternative...
            # TODO: Maybe GenericRelation could help, but that seems to insist deleting the referencing object
            # (Version) when the referenced object (user, registration) is deleted, which is not what we want.
            registrations=Subquery(
                ArtaUser.objects.filter(
                    # This uses a nested subquery to ensure each user is returned only once (since distinct() does not
                    # seem to work together with the GroupConcat aggregation)
                    pk__in=Subquery(
                        ArtaUser.objects.filter(
                            # This needs nested subqueries because there is no direct relation between Version and
                            # ArtaUser/Registration.
                            Q(pk__in=Subquery(
                                Version.objects.filter(
                                    revision=OuterRef(OuterRef(OuterRef('id'))),
                                    content_type=ContentType.objects.get_for_model(ArtaUser),
                                ).values('object_id'),
                            )) | Q(
                                registrations__in=Subquery(
                                    # TODO: filter event?
                                    Version.objects.filter(
                                        revision=OuterRef(OuterRef(OuterRef('id'))),
                                        content_type=ContentType.objects.get_for_model(Registration),
                                    ).values('object_id'),
                                ), registrations__event=self.event,
                            ),
                        ).values('id'),
                    ))
                .with_full_name()
                # This applies the trick documented to group *all* of the results of this subquery and return the names
                # concatenated, so this always returns a single result that can be annotated. See:
                # https://docs.djangoproject.com/en/4.1/ref/models/expressions/#using-aggregates-within-a-subquery-expression
                .order_by()
                .annotate(dummy=Value(0))
                .values('dummy')
                .annotate(concat_names=GroupConcat(Value('\n'), F('full_name')))
                .values("concat_names"),
            ),
        ).order_by('-date_created').select_related('user')

        return revisions
