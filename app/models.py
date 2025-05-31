from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class CardEvent(models.Model):
    card_id = models.CharField(max_length=64)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(default=timezone.now)
    def __str__(self):
        return f"Card: {self.card_id} for {self.user.username}"

class CardUser(models.Model):
    card_id = models.CharField(max_length=64, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    def __str__(self):
        return f"Card: {self.card_id} for {self.user.username}"
    

class PersonalAttendanceSetting(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    checkin_time = models.TimeField(verbose_name="Giờ vào ca")
    checkout_time = models.TimeField(verbose_name="Giờ ra ca")  

    class Meta:
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user.username} - {self.date}: {self.checkin_time} - {self.checkout_time}"
