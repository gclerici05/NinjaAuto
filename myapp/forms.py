from django import forms
from .models import Appointment, Availability

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'name', 'email', 'phone',
            'service', 'car_make', 'car_model', 'car_year',
            'availability', 'water', 'address', 'notes', 
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show unbooked slots
        self.fields['availability'].queryset = Availability.objects.filter(
            is_active=True,
            appointment__isnull=True
        ).order_by('date', 'time_slot')