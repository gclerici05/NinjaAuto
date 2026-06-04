
from django.contrib import admin
from .models import Availability, Appointment

@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ['date', 'time_slot', 'is_active', 'is_booked']
    list_filter = ['date', 'is_active']
    ordering = ['date', 'time_slot']

    def is_booked(self, obj):
        return hasattr(obj, 'appointment')
    is_booked.boolean = True

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'service', 'availability', 'email', 'phone', 'created_at']
    list_filter = ['service', 'availability__date']
    ordering = ['-created_at']