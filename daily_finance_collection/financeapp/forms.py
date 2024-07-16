from django import forms
from .models import Customer
from django.contrib.auth.forms import UserCreationForm
from .models import Employee, LoanDetail
from .models import DailyTransaction

class DailyTransactionForm(forms.ModelForm):
    class Meta:
        model = DailyTransaction
        fields = ['add_cash', 'expenses']

class LoginForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=100)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)
    user_type = forms.ChoiceField(choices=[('admin', 'Admin'), ('employee', 'Employee')], label='Select User Type')

class CustomerForm(forms.ModelForm):

    class Meta:
        model = Customer
        fields = ['customer_number', 'first_name', 'last_name', 'phone_number', 'address', 'loan_amount', 'photo']
        widgets = {
            'loan_amount': forms.Select(choices=[
                (5000, '5000'),
                (10000, '10000'),
                (15000, '15000'),
                (20000, '20000'),
                (25000, '25000'),
            ]),
        }

class EmployeeForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'empid', 'password']

class PaidAmountForm(forms.ModelForm):
    class Meta:
        model = LoanDetail
        fields = ['paid_amount']

class CustomerEditForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'address', 'phone_number']