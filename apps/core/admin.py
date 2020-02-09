from django.contrib import admin

from .models import ConsentLog


@admin.register(ConsentLog)
class ConsentLogAdmin(admin.ModelAdmin):
    # Admin is read-only, to prevent compromising log integrity.

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
