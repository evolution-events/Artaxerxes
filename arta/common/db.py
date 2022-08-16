from django.db import models


def QExpr(*args, **kwargs):
    """ Builds a Q object wrapped as an expression, to be used in e.g. annotate. """
    # This should really be handled by Django automatically, see https://code.djangoproject.com/ticket/27021
    return models.ExpressionWrapper(models.Q(*args, **kwargs), output_field=models.BooleanField())


class FromOuterRef:
    """
    Helper to allow using the same query for a direct or a subquery.

    A function that generates a query based on a model instance, and only uses direct fields of that model instance,
    can be passed an instance of FromOuterRef instead to generate a query with OuterRef fields instead.
    """

    def __init__(self, prefix=''):
        self.prefix = prefix

    def __getattr__(self, attr):
        return models.OuterRef(self.prefix + attr)


class UpdatedAtQuerySetMixin:
    def update(self, **kwargs):
        # TODO: This should be implemented if we need QuerySet.update, but for now just raise
        # See https://code.djangoproject.com/ticket/26239
        raise NotImplementedError("Update does not set updated_at / auto_now fields")


# Based on https://stackoverflow.com/a/38017535/740048
class GroupConcat(models.Aggregate):
    function = 'GROUP_CONCAT'
    template = '%(function)s(%(expressions)s)'

    def __init__(self, separator, expression, **kwargs):
        super().__init__(
            expression,
            separator,
            output_field=models.CharField(),
            **kwargs,
        )

    # This is a hack to prevent triggering the check fixed by
    # https://github.com/django/django/commit/cbb6531e5bef7ffe0c46d6c44d598d7bcdf9029e
    # TODO: Remove when upgrading to Django 3.1
    def as_sql(self, compiler, connection, **kwargs):
        old_check = connection.ops.check_expression_support
        try:
            connection.ops.check_expression_support = lambda self: None
            return super().as_sql(compiler, connection, **kwargs)
        finally:
            connection.ops.check_expression_support = old_check

    def as_mysql(self, *args, **kwargs):
        # This is a bit of a hack, but by replacing the normal comma arg_joiner we can make this work on mysql (which
        # needs the SEPARATOR keyword instead of comma-separated arguments like Sqlite). This relies on the fact that
        # we have only two expressions.
        return self.as_sql(*args, arg_joiner=' SEPARATOR ')
