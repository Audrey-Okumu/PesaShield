from django.db import models
import hashlib

class UserProfile(models.Model):
    phone_number = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=100, blank=True)
    pin_hash = models.CharField(max_length=64, blank=True, default='')  # SHA-256 hash of 4-digit PIN
    total_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Budget categories (remaining balances)
    food = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    accommodation = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    transport = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    savings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    other = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_pin(self, pin):
        """Hash the 4-digit PIN"""
        self.pin_hash = hashlib.sha256(pin.encode()).hexdigest()

    def check_pin(self, pin):
        """Verify PIN"""
        return self.pin_hash == hashlib.sha256(pin.encode()).hexdigest()

    def __str__(self):
        return f"{self.name} ({self.phone_number})"