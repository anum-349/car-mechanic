from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLES = [("user","User"),("mechanic","Mechanic"),
             ("reviewer","Reviewer"),("admin","Admin")]
    
    name = models.CharField(max_length=50, blank=False)
    email = models.EmailField(blank=False, unique=True)
    city = models.CharField(max_length=100)
    phone = models.CharField(max_length=11, unique=True)
    role = models.CharField(max_length=50, choices=ROLES, default='user')
    is_active = models.BooleanField(default=False)
    date_joined = models.DateField(auto_now_add=True)
 
class MechanicProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    workshop_name = models.CharField(max_length=100, unique=True, null=False)
    experience_years = models.PositiveSmallIntegerField(default=0)
    specialization = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    honesty_score = models.DecimalField(max_digits=3, default=0, decimal_places=1)