from django.db import models


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
        ('express', 'Express Detail - $89'),
        ('full', 'Full Detail - $249'),
        ('ceramic', 'Ceramic Coating - $699'),
        ('paint', 'Paint Correction - $399'),
        ('ppf', 'PPF Installation - $499'),
        ('elite', 'Elite Package - $1,299'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
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


class Manager(models.Model):
    id =  models.AutoField(primary_key=True)
    managerName = models.CharField(max_length=100)
    password = models.CharField(max_length=255)


# Create your models here.
