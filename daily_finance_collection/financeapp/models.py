from django.db import models
from datetime import date, timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
import uuid
from django.utils import timezone

class Customer(models.Model):
    customer_number = models.CharField(max_length=20, default='')
    first_name = models.CharField(max_length=100, default='')
    last_name = models.CharField(max_length=100, default='')
    address = models.TextField(default='')
    phone_number = models.CharField(max_length=15, default='')
    loan_amount = models.IntegerField(default=5000)
    per_day_emi = models.IntegerField(default=100)
    opening_date = models.DateField(default=date.today)
    closing_date = models.DateField(null=True, blank=True)
    total_amount = models.IntegerField(null=True, blank=True)
    emi_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    received_amount = models.IntegerField(default=0)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    photo = models.ImageField(upload_to='customer_photos/', null=True, blank=True)
    guarantor_name = models.CharField(max_length=100, blank=True, default='NA')
    guarantor_phone_number = models.CharField(max_length=15, blank=True, default='NA')

    def save(self, *args, **kwargs):
        if not self.customer_number:
            self.customer_number = str(uuid.uuid4()).split('-')[0]
        if self.opening_date and not self.closing_date:
            self.closing_date = self.opening_date + timedelta(days=52)
        loan_map = {
            5000: (100, 5200),
            10000: (200, 10400),
            15000: (300, 15600),
            20000: (400, 20800),
            25000: (500, 26000),
        }
        if self.loan_amount in loan_map:
            self.per_day_emi, self.total_amount = loan_map[self.loan_amount]
        self.emi_due = self.total_amount - self.loan_amount
        self.balance_due = self.total_amount - self.received_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class Employee(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15)
    empid = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=100)
    total_cash_picked = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cash_picked_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class EmployeeAssignment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date_assigned = models.DateField(default=date.today)

    def __str__(self):
        return f"{self.customer} assigned to {self.employee} on {self.date_assigned}"

class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    emi_date = models.DateField()
    per_day_emi = models.DecimalField(max_digits=10, decimal_places=2)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2)
    picked_by = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.customer.customer_number} - {self.emi_date}"
    
class LoanDetail(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    sr_no = models.IntegerField()
    date = models.DateField()
    opening_outstand = models.DecimalField(max_digits=10, decimal_places=2)
    dea = models.DecimalField(max_digits=10, decimal_places=2)
    closing_outstand = models.DecimalField(max_digits=10, decimal_places=2)
    status_paid_unpaid = models.CharField(max_length=10, blank=True, null=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    daily_collection_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def is_closing_outstanding_zero(self):
        return self.closing_outstand == 0

class DailyTransaction(models.Model):
    date = models.DateField(default=date.today)
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    daily_collection = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loan_distribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    add_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.closing_balance = (self.opening_balance + self.add_cash + self.daily_collection) - (self.expenses + self.loan_distribution)
        super().save(*args, **kwargs)

class GoogleAccount(models.Model):
    # pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

    email = models.EmailField(unique=True)
    credentials = models.TextField()