from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Availability, Appointment
from .forms import AppointmentForm
import json

def home(request):
    return render(request, 'home_update.html')

def booking(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('booking_success')
    else:
        service = request.GET.get('service', '')
        form = AppointmentForm(initial={'service': service})
    return render(request, 'booking.html', {'form': form})

def booking_success(request):
    return render(request, 'booking_success.html')

@require_GET
def available_slots(request):
    """Returns booked dates and all available slots as JSON for the calendar."""
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'No date provided'}, status=400)

    slots = Availability.objects.filter(
        date=date_str,
        is_active=True
    ).select_related('appointment')

    data = []
    for slot in slots:
        data.append({
            'id': slot.id,
            'time': slot.time_slot.strftime('%H:%M'),
            'booked': hasattr(slot, 'appointment'),
        })

    return JsonResponse({'slots': data})

@require_GET
def booked_dates(request):
    """Returns all fully booked dates for the calendar to grey out."""
    from django.db.models import Count, Q
    
    # Get dates where every active slot is booked
    dates = Availability.objects.filter(is_active=True).values('date').annotate(
        total=Count('id'),
        booked=Count('id', filter=Q(appointment__isnull=False))
    )

    fully_booked = [
        str(d['date']) for d in dates if d['total'] == d['booked'] and d['total'] > 0
    ]
    has_availability = [
        str(d['date']) for d in dates if d['total'] > d['booked']
    ]

    return JsonResponse({
        'fully_booked': fully_booked,
        'available': has_availability,
    })