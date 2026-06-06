"""
URL configuration for detailingProject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from myapp import views 

from django.urls import path
from myapp.views import *

secret_key = 'GTWqoK1ATI5WvTMN'
urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('booking/', views.booking, name='booking'),
    path('booking/success/', views.booking_success, name='booking_success'),

    # API - Calendar
    path('api/slots/', views.available_slots, name='available_slots'),
    path('api/booked-dates/', views.booked_dates, name='booked_dates'),

    # API - Appointments
    path('send-confirmation/<int:appointment_id>/', views.send_confirmation, name='send_confirmation'),
    path('cancel-appointment/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),

    # Manager pages
    path('ninja-admin/register/<str:secret_key>/', views.create_manager_page, name='create_manager_page'),
    path('ninja-admin/login/', views.manager_login_page, name='manager_login'),
    path('ninja-admin/dashboard/', views.dashboard, name='dashboard'),
    path('ninja-admin/logout/', views.manager_logout, name='manager_logout'),
    path('forgot-password/', views.forgot_password_page, name='forgot_password'),

    # API - Manager
    path('api/manager/create/', views.create_manager, name='create_manager'),
    path('api/manager/login/', views.manager_login, name='manager_login_api'),
    path('api/manager/change-password/', views.change_password, name='change_password'),
    path('api/manager/appointments/', views.appointment_dashboard, name='appointment_dashboard'),
    path('api/manager/availability/', views.create_availability, name='create_availability'),
    path('api/manager/forgot-password/', views.email_forgot_password_link, name='email_forgot_password'),
]