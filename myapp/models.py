from django.db import models
import datetime
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

class Manager(models.Model):
    id =  models.AutoField(primary_key=True)
    managerName = models.CharField(max_length=100)
    managerEmail = models.EmailField(default= 'null@null.com', unique=True, validators=[EmailValidator(message="Please enter a valid email address.")])
    password = models.CharField(max_length=255)
    locked = models.BooleanField(default=False)

class ManagerLoginAttempt(models.Model):
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)

class Availability(models.Model):
    date = models.DateField()
    time_slot = models.TimeField()
    is_active = models.BooleanField(default=True)  # admin can disable slots

    class Meta:
        unique_together = ('date', 'time_slot')
        ordering = ['date', 'time_slot']

    def __str__(self):
        return f"{self.date} at {self.time_slot}"


class Appointment(models.Model):
    SERVICE_CHOICES = [
        ('exterior', 'Standard Exterior Detail - $49.99'),
        ('interior', 'Standard Interior Detail - $59.99'),
        ('express', 'Standard Express Detail - $99.99'),
        ('premium', 'Premium Care Detail - $119.99–$169.99'),
        ('elite', 'Elite Package Detail - $159.99–$219.99'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, validators=[EmailValidator(message="Please enter a valid email address.")])
    phone = models.CharField(max_length=20)
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    car_make = models.CharField(max_length=50)
    car_model = models.CharField(max_length=50)
    car_year = models.IntegerField()
    availability = models.OneToOneField(
        Availability, on_delete=models.PROTECT, related_name='appointment'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} – {self.service} on {self.availability.date}"




# Create your models here.
