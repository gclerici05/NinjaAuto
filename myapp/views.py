from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from .models import Availability, Appointment, Manager, ManagerLoginAttempt
from .forms import AppointmentForm
from django.contrib.auth.hashers import make_password, check_password
from datetime import datetime
from django.core.mail import send_mail
import json


@csrf_exempt
def create_manager(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        Manager.objects.create(
            managerName=data['managerName'],
            managerEmail=data['managerEmail'],
            password=make_password(data['password']),
            locked=False
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid method'}, status=400)


@csrf_exempt
def manager_login(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        try:
            manager = Manager.objects.get(managerEmail=data['managerEmail'])

            if manager.locked:
                return JsonResponse({
                    'status': 'failure',
                    'message': 'Account is locked due to too many failed login attempts. Please reset your password.'
                }, status=403)

            # Correct password check
            if check_password(data['password'], manager.password):

                # Record successful login
                ManagerLoginAttempt.objects.create(
                    manager=manager,
                    success=True,
                    timestamp=datetime.now()
                )

                request.session['manager_id'] = manager.id
                request.session['manager_email'] = manager.managerEmail

                return JsonResponse({
                    'status': 'success',
                    'message': 'Login successful',
                    'forgot_password_url': '/forgot-password/'
                })

            # Count failed attempts
            log_in_attempt = 0
            for attempt in ManagerLoginAttempt.objects.filter(manager=manager).order_by('-timestamp')[:5]:
                if attempt.success:
                    break
                log_in_attempt += 1

            # Record failed attempt
            ManagerLoginAttempt.objects.create(
                manager=manager,
                success=False,
                timestamp=datetime.now()
            )

            # Show forgot password after 3 attempts
            if log_in_attempt >= 2:
                return JsonResponse({
                    'status': 'failure',
                    'message': 'Invalid password',
                    'forgot_password_url': '/forgot-password/'
                }, status=401)

            # Lock account after 4 failed attempts
            if log_in_attempt >= 3:
                manager.locked = True
                manager.save()
                return JsonResponse({
                    'status': 'failure',
                    'message': 'Account locked due to too many failed attempts.',
                    'forgot_password_url': '/forgot-password/'
                }, status=403)

            return JsonResponse({
                'status': 'failure',
                'message': 'Invalid password'
            }, status=401)

        except Manager.DoesNotExist:
            return JsonResponse({
                'status': 'failure',
                'message': 'Invalid email or password'
            }, status=404)

    return JsonResponse({'status': 'invalid method'}, status=400)


@csrf_exempt
def change_password(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        try:
            manager = Manager.objects.get(managerEmail=data['managerEmail'])
            manager.password = make_password(data['newPassword'])
            manager.locked = False
            manager.save()
            return JsonResponse({'status': 'success'})

        except Manager.DoesNotExist:
            return JsonResponse({'status': 'failure'}, status=404)

    return JsonResponse({'status': 'invalid method'}, status=400)

def manager_logout(request):
    request.session.flush()
    return JsonResponse({'status': 'success', 'message': 'Logged out successfully'})

def email_forgot_password_link(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            manager = Manager.objects.get(managerEmail=data['managerEmail'])
            # Here you would normally send an email with a reset link
            send_mail(
                'Password Reset Request',
                'Click the link to reset your password: http://gclerici.pythonanywhere.com/reset-password/',
                'liam@ninjaautodetailingsd.com',
                [manager.managerEmail],
                fail_silently=False,
            )
            return JsonResponse({'status': 'success', 'message': 'Password reset link sent to your email'})
        except Manager.DoesNotExist:
            return JsonResponse({'status': 'failure', 'message': 'Email not found'}, status=404)
    return JsonResponse({'status': 'invalid method'}, status=400)

def appointment_dashboard(request):
    if 'manager_id' not in request.session:
        return JsonResponse({'status': 'failure', 'message': 'Unauthorized'}, status=401)

    appointments = Appointment.objects.select_related('availability').order_by('-created_at')
    data = []
    for appt in appointments:
        data.append({
            'id': appt.id,
            'name': appt.name,
            'email': appt.email,
            'phone': appt.phone,
            'service': appt.service,
            'car_make': appt.car_make,
            'car_model': appt.car_model,
            'car_year': appt.car_year,
            'date': appt.availability.date.strftime('%Y-%m-%d'),
            'time_slot': appt.availability.time_slot.strftime('%H:%M'),
            'notes': appt.notes,
            'created_at': appt.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return JsonResponse({'status': 'success', 'appointments': data})

def dashboard(request):
    if 'manager_id' not in request.session:
        return redirect('/ninja-admin/login/')  # ← use URL directly
    return render(request, 'dashboard.html')

def create_availability(request):
    if 'manager_id' not in request.session:
        return JsonResponse({'status': 'failure'}, status=401)
    if request.method == 'POST':
        date = request.POST.get('date')
        time_slot = request.POST.get('time_slot')
        Availability.objects.create(date=date, time_slot=time_slot)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid method'}, status=400)
def home(request):
    return render(request, 'home_update.html')

def booking(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appt = form.save()
            request.session['last_appointment_id'] = appt.id
            return redirect('booking_success')
    else:
        service = request.GET.get('service', '')
        form = AppointmentForm(initial={'service': service})
    return render(request, 'booking.html', {'form': form})

def send_booking_confirmation_email(appointment):
    send_mail(
        'Appointment Confirmation',
        f'Hello {appointment.name}, your appointment is confirmed for {appointment.availability.date} at {appointment.availability.time_slot}. Service: {appointment.service}.',
        'liam@ninjaautodetailingsd.com',
        [appointment.email],
        fail_silently=False,
    )

def send_confirmation(request, appointment_id):
    try:
        appointment = Appointment.objects.get(id=appointment_id)
        send_booking_confirmation_email(appointment)
        return JsonResponse({'status': 'success', 'message': 'Confirmation email sent'})
    except Appointment.DoesNotExist:
        return JsonResponse({'status': 'failure', 'message': 'Appointment not found'}, status=404)


def booking_success(request):
    appointment_id = request.session.get('last_appointment_id')

    if appointment_id:
        appointment = Appointment.objects.get(id=appointment_id)

        # Email to manager with quick-action link
        send_mail(
            'New Appointment Booked',
            f'A new appointment has been booked.\n\n'
            f'Customer: {appointment.name}\n'
            f'Date: {appointment.availability.date}\n'
            f'Time: {appointment.availability.time_slot}\n'
            f'Service: {appointment.service}\n\n'
            f'Click below to send the confirmation email to the customer:\n'
            f'http://gclerici.pythonanywhere.com/send-confirmation/{appointment.id}/',
            'liam@ninjaautodetailingsd.com',
            ['liam@ninjaautodetailingsd.com'],
            fail_silently=False,
        )

        # Email to customer (initial message)
        send_mail(
            'Your Appointment is Confirmed',
            f'Thank you for booking with Ninja Auto Detailing! We will soon send you a confirmation email.\n\n'
            f'Appointment Details:\n'
            f'Customer: {appointment.name}\n'
            f'Date: {appointment.availability.date}\n'
            f'Time: {appointment.availability.time_slot}\n'
            f'Service: {appointment.service}\n',
            'liam@ninjaautodetailingsd.com',
            [appointment.email],
            fail_silently=True,
        )

    return render(request, 'booking_success.html')

def cancel_appointment(request, appointment_id):
    try:
        appointment = Appointment.objects.get(id=appointment_id)
        appointment.availability.is_active = True
        appointment.availability.save()
        appointment.delete()
        return JsonResponse({'status': 'success', 'message': 'Appointment cancelled'})
    except Appointment.DoesNotExist:
        return JsonResponse({'status': 'failure', 'message': 'Appointment not found'}, status=404)

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

def create_manager_page(request, secret_key):
    if secret_key != 'GTWqoK1ATI5WvTMN':
        return HttpResponseForbidden()
    return render(request, 'create_manager.html')

def manager_login_page(request):
    if 'manager_id' in request.session:
        return redirect('dashboard')
    return render(request, 'manager_login.html')

def forgot_password_page(request):
    return render(request, 'forgot_password.html')