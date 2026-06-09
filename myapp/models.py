from django.db import models
from django.core.validators import EmailValidator
import uuid

SERVICE_CHOICES = [
    ('exterior', 'Standard Exterior Detail'),
    ('interior', 'Standard Interior Detail'),
    ('express', 'Standard Express Detail'),
    ('premium', 'Premium Care Detail'),
    ('elite', 'Elite Package Detail'),
]


class Manager(models.Model):
    id = models.AutoField(primary_key=True)
    managerName = models.CharField(max_length=100)
    managerEmail = models.EmailField(
        default='null@null.com', unique=True,
        validators=[EmailValidator(message="Please enter a valid email address.")]
    )
    password = models.CharField(max_length=255)
    locked = models.BooleanField(default=False)

    def __str__(self):
        return self.managerName


class ManagerLoginAttempt(models.Model):
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)


class Availability(models.Model):
    date = models.DateField()
    time_slot = models.TimeField()
    is_active = models.BooleanField(default=True)
    duration_minutes = models.IntegerField(default=0)
    group_id = models.UUIDField(default=uuid.uuid4, editable=False)
    is_primary = models.BooleanField(default=False)  # ← NEW: True only on the start slot

    class Meta:
        unique_together = ('date', 'time_slot')
        ordering = ['date', 'time_slot']

    def __str__(self):
        return f"{self.date} at {self.time_slot.strftime('%H:%M')}"


class ServicePrice(models.Model):
    service = models.CharField(max_length=50, unique=True)  # removed choices= so admin can add freely
    name = models.CharField(max_length=100, blank=True)     # ← NEW: display name shown on homepage
    price_from = models.DecimalField(max_digits=8, decimal_places=2)
    price_to = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    suffix = models.CharField(max_length=100, default='per vehicle')
    description = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.name or self.service}: ${self.price_from}"


class Appointment(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(
        max_length=254,
        validators=[EmailValidator(message="Please enter a valid email address.")]
    )
    phone = models.CharField(max_length=20)
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    car_make = models.CharField(max_length=50)
    car_model = models.CharField(max_length=50)
    car_year = models.IntegerField()
    availability = models.OneToOneField(
        Availability, on_delete=models.PROTECT, related_name='appointment'
    )
    address = models.CharField(max_length=200, blank=True)
    water = models.TextField(default='no')  # ← NEW: store water hose info as text for flexibility
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} – {self.service} on {self.availability.date}"