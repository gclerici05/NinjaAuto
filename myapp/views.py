from urllib import request

from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
import json
import uuid

from .models import Availability, Appointment, Manager, ManagerLoginAttempt, ServicePrice
from .forms import AppointmentForm


# ── Helpers ──────────────────────────────────────────────────────────────────

def format_duration(minutes):
    if not minutes:
        return "1h"
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h {m}m"
    return f"{h}h" if h else f"{m}m"


def require_manager(view_fn):
    """Decorator: returns 401 JSON if manager not logged in."""
    def wrapper(request, *args, **kwargs):
        if "manager_id" not in request.session:
            return JsonResponse({"status": "failure", "error": "Unauthorized"}, status=401)
        return view_fn(request, *args, **kwargs)
    return wrapper


def primary_slots(exclude_group_id=None):
    """Returns active primary (start) slots, optionally excluding one group."""
    qs = Availability.objects.filter(is_active=True, is_primary=True)
    if exclude_group_id:
        qs = qs.exclude(group_id=exclude_group_id)
    return qs.order_by("date", "time_slot")


def slot_label(slot):
    return (
        f"{slot.date.strftime('%b %d, %Y')} at {slot.time_slot.strftime('%H:%M')} "
        f"({format_duration(slot.duration_minutes)})"
    )


def appointment_to_dict(appt):
    return {
        "id": appt.id,
        "name": appt.name,
        "email": appt.email,
        "phone": appt.phone,
        "service": appt.service,
        "car_make": appt.car_make,
        "car_model": appt.car_model,
        "car_year": appt.car_year,
        "date": appt.availability.date.strftime("%Y-%m-%d"),
        "time_slot": appt.availability.time_slot.strftime("%H:%M"),
        "duration": format_duration(appt.availability.duration_minutes),
        "water": appt.water,
        "address": appt.address,
        "notes": appt.notes,
        "created_at": appt.created_at.strftime("%Y-%m-%d %H:%M"),
    }


# ── Pages ─────────────────────────────────────────────────────────────────────

def home(request):
    return render(request, "home_update.html")


def dashboard(request):
    if "manager_id" not in request.session:
        return redirect("/ninja-admin/login/")
    return render(request, "dashboard.html")


def manager_login_page(request):
    if "manager_id" in request.session:
        return redirect("dashboard")
    return render(request, "manager_login.html")


def forgot_password_page(request):
    return render(request, "forgot_password.html")


def create_manager_page(request, secret_key):
    if secret_key != "GTWqoK1ATI5WvTMN":
        return HttpResponseForbidden()
    return render(request, "create_manager.html")


# ── Auth ──────────────────────────────────────────────────────────────────────

@csrf_exempt
def create_manager(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)
    data = json.loads(request.body)
    Manager.objects.create(
        managerName=data["managerName"],
        managerEmail=data["managerEmail"],
        password=make_password(data["password"]),
    )
    return JsonResponse({"status": "success"})


@csrf_exempt
def manager_login(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)

    data = json.loads(request.body)
    try:
        manager = Manager.objects.get(managerEmail=data["managerEmail"])
    except Manager.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Invalid email or password"}, status=404)

    if manager.locked:
        return JsonResponse({"status": "failure", "message": "Account locked. Please reset your password."}, status=403)

    if check_password(data["password"], manager.password):
        ManagerLoginAttempt.objects.create(manager=manager, success=True)
        request.session.update({
            "manager_id": manager.id,
            "manager_email": manager.managerEmail,
            "manager_name": manager.managerName,
        })
        return JsonResponse({"status": "success", "message": "Login successful"})

    # Failed login — count consecutive failures
    ManagerLoginAttempt.objects.create(manager=manager, success=False)
    recent = ManagerLoginAttempt.objects.filter(manager=manager).order_by("-timestamp")[:5]
    failures = 0
    for attempt in recent:
        if attempt.success:
            break
        failures += 1

    if failures >= 3:
        manager.locked = True
        manager.save()
        return JsonResponse(
            {"status": "failure", "message": "Account locked due to too many failed attempts.", "forgot_password_url": "/forgot-password/"},
            status=403,
        )

    extra = {"forgot_password_url": "/forgot-password/"} if failures >= 2 else {}
    return JsonResponse({"status": "failure", "message": "Invalid password", **extra}, status=401)


@csrf_exempt
def change_password(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)
    data = json.loads(request.body)
    try:
        manager = (
            Manager.objects.get(id=request.session["manager_id"])
            if data.get("managerEmail") == "__session__"
            else Manager.objects.get(managerEmail=data["managerEmail"])
        )
        manager.password = make_password(data["newPassword"])
        manager.locked = False
        manager.save()
        return JsonResponse({"status": "success"})
    except (Manager.DoesNotExist, KeyError):
        return JsonResponse({"status": "failure"}, status=404)


def manager_logout(request):
    request.session.flush()
    return JsonResponse({"status": "success", "message": "Logged out"})


@csrf_exempt
def email_forgot_password_link(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)
    data = json.loads(request.body)
    try:
        manager = Manager.objects.get(managerEmail=data["managerEmail"])
        send_mail(
            "Password Reset Request",
            "Click the link to reset your password: http://gclerici.pythonanywhere.com/reset-password/",
            "liam@ninjaautodetailingsd.com",
            [manager.managerEmail],
        )
        return JsonResponse({"status": "success", "message": "Reset link sent"})
    except Manager.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Email not found"}, status=404)


# ── Availability ──────────────────────────────────────────────────────────────

@csrf_exempt
@require_manager
def create_availability(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)

    date = request.POST.get("date")
    time_slot = request.POST.get("time_slot")
    try:
        duration = int(request.POST.get("duration", 60))
    except ValueError:
        return JsonResponse({"status": "failure", "error": "Invalid duration"}, status=400)

    if not date or not time_slot:
        return JsonResponse({"status": "failure", "error": "Missing fields"}, status=400)

    start_time = datetime.strptime(time_slot, "%H:%M").time()
    blocks = max(1, (duration + 59) // 60)

    # Build all slot times and check for conflicts before writing anything
    slot_times = []
    for i in range(blocks):
        t = (datetime.combine(datetime.today(), start_time) + timedelta(hours=i)).time()
        if Availability.objects.filter(date=date, time_slot=t).exists():
            return JsonResponse(
                {"status": "conflict", "error": f"Slot already exists at {t.strftime('%H:%M')}"},
                status=409,
            )
        slot_times.append(t)

    group_id = uuid.uuid4()
    slots = Availability.objects.bulk_create([
        Availability(
            date=date,
            time_slot=t,
            group_id=group_id,
            duration_minutes=duration if i == 0 else 0,
            is_primary=(i == 0),
        )
        for i, t in enumerate(slot_times)
    ])

    return JsonResponse({"status": "success", "primary_id": slots[0].id})


def delete_availability(request, availability_id):
    if "manager_id" not in request.session:
        return JsonResponse({"status": "failure"}, status=401)
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)
    try:
        slot = Availability.objects.get(id=availability_id)
        Availability.objects.filter(group_id=slot.group_id).delete()
        return JsonResponse({"status": "success"})
    except Availability.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Not found"}, status=404)



@require_GET
def available_slots(request):
    date_str = request.GET.get("date")
    if not date_str:
        return JsonResponse({"error": "No date provided"}, status=400)

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    slots = Availability.objects.filter(
        date=date_obj,
        is_primary=True
    ).order_by("time_slot")

    result = []

    for s in slots:
        duration = s.duration_minutes or 60

        start_dt = datetime.combine(s.date, s.time_slot)
        end_dt = start_dt + timedelta(minutes=duration)

        result.append({
            "id": s.id,
            "group_id": str(s.group_id),
            "booked": not s.is_active,

            # 🔥 SAME STYLE AS DASHBOARD
            "label": slot_label(s),

            # optional raw values
            "time": s.time_slot.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M"),
            "duration": format_duration(duration),
        })

    return JsonResponse({"slots": result})


@require_GET
def booked_dates(request):
    dates = (
        Availability.objects.filter(is_primary=True)
        .values("date")
        .annotate(
            total=Count("id"),
            available=Count("id", filter=Q(is_active=True)),
        )
    )
    fully_booked = [str(d["date"]) for d in dates if d["available"] == 0]
    has_availability = [str(d["date"]) for d in dates if d["available"] > 0]
    return JsonResponse({"fully_booked": fully_booked, "available": has_availability})


# ── Appointments ──────────────────────────────────────────────────────────────

def booking(request):
    if request.method == "POST":
        form = AppointmentForm(request.POST)
        form.fields["availability"].queryset = primary_slots()
        if form.is_valid():
            availability = form.cleaned_data["availability"]
            group_slots = Availability.objects.filter(group_id=availability.group_id)
            if group_slots.filter(is_active=False).exists():
                form.add_error("availability", "This slot is no longer available.")
            else:
                with transaction.atomic():
                    appt = form.save()
                    appt = form.save(commit=False)
                    appt.water = request.POST.get("water", "no")
                    group_slots.update(is_active=False)
                request.session["last_appointment_id"] = appt.id
                return redirect("booking_success")
    else:
        form = AppointmentForm(initial={"service": request.GET.get("service", "")})
        form.fields["availability"].queryset = primary_slots()

    form.fields["availability"].label_from_instance = slot_label
    return render(request, "booking.html", {"form": form})


def reschedule_appointment(request, appointment_id):
    appointment = Appointment.objects.select_related("availability").get(id=appointment_id)
    available = primary_slots(exclude_group_id=appointment.availability.group_id)

    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=appointment)
        form.fields["availability"].queryset = available
        if form.is_valid():
            new_avail = form.cleaned_data["availability"]
            with transaction.atomic():
                Availability.objects.filter(group_id=appointment.availability.group_id).update(is_active=True)
                Availability.objects.filter(group_id=new_avail.group_id).update(is_active=False)
                form.save()
            return redirect("booking_success")
    else:
        form = AppointmentForm(instance=appointment)
        form.fields["availability"].queryset = available

    form.fields["availability"].label_from_instance = slot_label
    return render(request, "reschedule_appointment.html", {"form": form, "appointment": appointment})


def cancel_appointment(request, appointment_id):
    try:
        appointment = Appointment.objects.get(id=appointment_id)
        group_id = appointment.availability.group_id
        appointment.delete()
        Availability.objects.filter(group_id=group_id).update(is_active=True)
        return JsonResponse({"status": "success", "message": "Appointment cancelled"})
    except Appointment.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Appointment not found"}, status=404)


@require_manager
def appointment_dashboard(request):
    appointments = Appointment.objects.select_related("availability").order_by("-created_at")
    return JsonResponse({"status": "success", "appointments": [appointment_to_dict(a) for a in appointments]})


@csrf_exempt
@require_manager
def delete_past_appointments(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)
    now = timezone.now()
    past = Appointment.objects.select_related("availability").filter(
        Q(availability__date__lt=now.date()) |
        Q(availability__date=now.date(), availability__time_slot__lt=now.time())
    )
    group_ids = list(past.values_list("availability__group_id", flat=True))
    count = past.count()
    past.delete()
    Availability.objects.filter(group_id__in=group_ids).delete()
    return JsonResponse({"status": "success", "deleted": count})


# ── Email ─────────────────────────────────────────────────────────────────────

def send_confirmation(request, appointment_id):
    try:
        appt = Appointment.objects.get(id=appointment_id)
        send_mail(
            "Appointment Confirmation",
            f"Hello {appt.name}, your appointment is confirmed for "
            f"{appt.availability.date} at {appt.availability.time_slot}. "
            f"Service: {appt.get_service_display()}.",
            "liam@ninjaautodetailingsd.com",
            [appt.email],
        )
        return JsonResponse({"status": "success", "message": "Confirmation email sent"})
    except Appointment.DoesNotExist:
        return JsonResponse({"status": "failure", "message": "Appointment not found"}, status=404)


def booking_success(request):
    appt_id = request.session.get("last_appointment_id")
    if appt_id:
        try:
            appt = Appointment.objects.select_related("availability").get(id=appt_id)
            base_url = "http://gclerici.pythonanywhere.com"
            send_mail(
                "New Appointment Booked",
                f"New booking:\n\n"
                f"Customer: {appt.name}\n"
                f"Phone: {appt.phone}\n"
                f"Email: {appt.email}\n"
                f"Date: {appt.availability.date}\n"
                f"Time: {appt.availability.time_slot}\n"
                f"Duration: {format_duration(appt.availability.duration_minutes)}\n"
                f"Service: {appt.get_service_display()}\n\n"
                f"Send confirmation: {base_url}/send-confirmation/{appt.id}/",
                "liam@ninjaautodetailingsd.com",
                ["liam@ninjaautodetailingsd.com"],
                fail_silently=True,
            )
            send_mail(
                "Your Appointment is Confirmed",
                f"Thank you for booking with Ninja Auto Detailing!\n\n"
                f"Name: {appt.name}\n"
                f"Date: {appt.availability.date}\n"
                f"Time: {appt.availability.time_slot}\n"
                f"Service: {appt.get_service_display()}\n\n"
                f"To cancel: {base_url}/cancel-appointment/{appt.id}/",
                "liam@ninjaautodetailingsd.com",
                [appt.email],
                fail_silently=True,
            )
        except Appointment.DoesNotExist:
            pass
    return render(request, "booking_success.html")


# ── Services & Prices ─────────────────────────────────────────────────────────

@require_GET
def get_prices(request):
    data = {
        p.service: {
            "name": p.name,
            "price_from": str(p.price_from),
            "price_to": str(p.price_to) if p.price_to else None,
            "suffix": p.suffix,
            "description": p.description,
        }
        for p in ServicePrice.objects.all()
    }
    return JsonResponse({"prices": data})


@csrf_exempt
@require_manager
def update_price(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)
    data = json.loads(request.body)
    obj, _ = ServicePrice.objects.get_or_create(service=data["service"])
    obj.name = data.get("name", data["service"])
    obj.price_from = data["price_from"]
    obj.price_to = data.get("price_to") or None
    obj.suffix = data.get("suffix", "per vehicle")
    obj.description = data.get("description", "")
    obj.save()
    return JsonResponse({"status": "success"})


@csrf_exempt
@require_manager
def delete_service(request):
    if request.method != "POST":
        return JsonResponse({"status": "invalid method"}, status=400)
    data = json.loads(request.body)
    deleted, _ = ServicePrice.objects.filter(service=data["service"]).delete()
    if deleted:
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "failure", "message": "Service not found"}, status=404)