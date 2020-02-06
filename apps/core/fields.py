from django.conf import settings
from django.db import models


class MonetaryField(models.DecimalField):
    """ This field class specifies a monetary value """

    description = "A monetary value of fixed currency"

    def __init__(self, *args, **kwargs):
        kwargs['decimal_places'] = settings.MONETARY_DECIMAL_PLACES
        kwargs['max_digits'] = settings.MONETARY_MAX_DIGITS
        super().__init__(*args, **kwargs)
