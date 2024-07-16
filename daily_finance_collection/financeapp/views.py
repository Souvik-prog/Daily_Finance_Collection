# Create your views here.

import csv
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from .forms import LoginForm
from django.contrib.auth.decorators import login_required
from .models import Customer, Employee, Payment, EmployeeAssignment, LoanDetail, DailyTransaction
from datetime import date
from .forms import CustomerForm, PaidAmountForm, CustomerEditForm
from .forms import EmployeeForm
from django.db.models import Sum
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
import pandas as pd
import datetime
from datetime import timedelta
from django.db import connection
from .forms import DailyTransactionForm
from django.core.paginator import Paginator
import os
from django.shortcuts import render, redirect
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .models import GoogleAccount
from django.conf import settings


# Path to the SQLite database
DB_PATH = os.path.join(settings.BASE_DIR, 'db.sqlite3')

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def google_login(request):
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    flow.redirect_uri = request.build_absolute_uri('/google-callback/')
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    request.session['state'] = state
    return redirect(authorization_url)

def google_callback(request):
    state = request.session['state']
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES, state=state)
    flow.redirect_uri = request.build_absolute_uri('/google-callback/')
    authorization_response = request.build_absolute_uri()
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    google_account = GoogleAccount(
        email=credentials.id_token['email'],
        credentials=credentials.to_json()
    )
    google_account.save()
    return redirect('data_backup')

@login_required
def data_backup(request):
    accounts = GoogleAccount.objects.all()
    return render(request, 'financeapp/data_backup.html', {'accounts': accounts})

def backup_to_drive(request, account_id):
    google_account = GoogleAccount.objects.get(id=account_id)
    credentials = Credentials.from_authorized_user_info(
        google_account.credentials)

    service = build('drive', 'v3', credentials=credentials)

    folder_metadata = {
        'name': datetime.date.today().isoformat(),
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    folder_id = folder.get('id')

    file_metadata = {
        'name': 'db.sqlite3',
        'parents': [folder_id]
    }
    media = MediaFileUpload(DB_PATH, mimetype='application/x-sqlite3')
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

    return redirect('data_backup')

def generate_excel(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    loan_details = LoanDetail.objects.filter(customer=customer).order_by('sr_no')

    # Create a CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename=loan_details_{customer.customer_number}.csv'

    writer = csv.writer(response)

    # Write customer details
    writer.writerow(['Customer Number', customer.customer_number])
    writer.writerow(['Customer Name', f"{customer.first_name} {customer.last_name}"])
    writer.writerow(['Phone Number', customer.phone_number])
    writer.writerow(['Address', customer.address])
    writer.writerow(['Total Amount', customer.total_amount])
    writer.writerow(['Per Day EMI', customer.per_day_emi])
    writer.writerow(['Opening Date', customer.opening_date])
    writer.writerow([])  # Blank line for separation

    # Write loan details header
    writer.writerow(['SR No', 'Date', 'Opening Outstand', 'DEA', 'Daily Collection Amount', 'Closing Outstand', 'Status Paid / Unpaid', 'Balance Amount'])

    # Write loan details rows
    for detail in loan_details:
        writer.writerow([
            detail.sr_no,
            detail.date,
            detail.opening_outstand,
            detail.dea,
            detail.daily_collection_amount,
            detail.closing_outstand,
            detail.status_paid_unpaid,
            detail.balance_amount
        ])

    return response

@login_required
def dashboard_view(request):
    total_employees = Employee.objects.count()
    total_customers = Customer.objects.count()

    # Fetch today's daily transaction
    today = date.today()
    daily_transaction = DailyTransaction.objects.filter(date=today).first()
    loan_details = LoanDetail.objects.filter(date=today)

    total_daily_collection = 0
    paid_amount = 0
    for detail in loan_details:
        total_daily_collection += detail.daily_collection_amount
        paid_amount += detail.paid_amount

    if not daily_transaction:
        daily_transaction = DailyTransaction(date=today, opening_balance=0)
        daily_transaction.save()

    opening_balance = daily_transaction.opening_balance
    closing_balance = daily_transaction.closing_balance
    daily_collection = total_daily_collection
    total_paid_amount = paid_amount

    total_market_cash = LoanDetail.objects.filter(date=date.today()).aggregate(Sum('opening_outstand'))['opening_outstand__sum'] or 0

    total_opening_outstand = total_market_cash
    total_closing_outstand = total_market_cash - total_paid_amount

    total_npa_amount = daily_collection - total_paid_amount

    if request.method == 'POST':
        new_opening_balance = request.POST.get('new_opening_balance')
        if new_opening_balance:
            daily_transaction.opening_balance = int(new_opening_balance)
            daily_transaction.save()
            opening_balance = daily_transaction.opening_balance

        if 'mark_holiday' in request.POST:
            mark_tomorrow_as_holiday()
            messages.success(request, 'Tomorrow has been marked as a holiday, and all dates have been adjusted accordingly.')

    context = {
        'total_employees': total_employees,
        'total_customers': total_customers,
        'opening_balance': opening_balance,
        'closing_balance': closing_balance,
        'total_opening_outstand': total_opening_outstand,
        'total_closing_outstand': total_closing_outstand,
        'daily_collection': daily_collection,
        'total_paid_amount': total_paid_amount,
        'total_npa_amount': total_npa_amount,
        'total_market_cash': total_market_cash,
    }

    return render(request, 'financeapp/dashboard.html', context)

def mark_tomorrow_as_holiday():
    tomorrow = timezone.now().date() + timezone.timedelta(days=1)
    active_customers = Customer.objects.filter(closing_date__gt=timezone.now().date())

    for customer in active_customers:
        customer.closing_date += timezone.timedelta(days=1)
        customer.save()

    active_loan_details = LoanDetail.objects.filter(date__gt=timezone.now().date())

    for detail in active_loan_details:
        if detail.date == date.today():
            continue
        detail.date += timezone.timedelta(days=1)
        detail.save()

@login_required
def add_customer_view(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST, request.FILES)
        if form.is_valid():
            customer_number = form.cleaned_data['customer_number']
            existing_customers = Customer.objects.filter(customer_number=customer_number)

            # Check for any existing customer with pending loans
            for existing_customer in existing_customers:
                if LoanDetail.objects.filter(customer=existing_customer, closing_outstand__gt=0).exists():
                    messages.error(request, 'Customer has a pending loan.')
                    return render(request, 'financeapp/add_customer.html', {'form': form})

            # Save the new customer
            customer = form.save()

            # Create loan details entries
            loan_amount = customer.loan_amount
            per_day_emi = customer.per_day_emi
            opening_outstand = customer.total_amount
            closing_outstand = opening_outstand - per_day_emi

            for i in range(1, 53):
                date = customer.opening_date + datetime.timedelta(days=i)
                LoanDetail.objects.create(
                    customer=customer,
                    sr_no=i,
                    date=date,
                    opening_outstand=opening_outstand,
                    dea=per_day_emi,
                    daily_collection_amount = per_day_emi,
                    closing_outstand=closing_outstand,
                    status_paid_unpaid=''
                )
                opening_outstand -= per_day_emi
                closing_outstand -= per_day_emi

            messages.success(request, 'Customer added successfully!')
            return redirect('customers_list')
    else:
        form = CustomerForm()

    return render(request, 'financeapp/add_customer.html', {'form': form})



@login_required
def customers_list_view(request):
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'active')
    today = timezone.now().date()

    if search_query:
        customers = Customer.objects.filter(customer_number=search_query)
    else:
        if status_filter == 'active':
            customers = Customer.objects.filter(closing_date__gt=today)
        elif status_filter == 'completed':
            customers = Customer.objects.filter(closing_date__lt=today, balance_due=0)
        elif status_filter == 'defaulters':
            customers = Customer.objects.filter(closing_date__lt=today, balance_due__gt=0)
        else:
            customers = Customer.objects.all()

    paginator = Paginator(customers, 2)  # Show 2 customers per page.
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'customers': customers,
        'page_obj': page_obj,
        'status_filter': status_filter
    }
    return render(request, 'financeapp/customers_list.html', context)


@login_required
def add_employee_view(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('employees_list')  # Redirect to a page showing the list of employees
    else:
        form = EmployeeForm()
    return render(request, 'financeapp/add_employee.html', {'form': form})

@login_required
def employees_list_view(request):
    employees = Employee.objects.all()
    return render(request, 'financeapp/employees_list.html', {'employees': employees})

@login_required
def edit_employee_view(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            return redirect('employees_list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'financeapp/edit_employee.html', {'form': form})

@login_required
def delete_employee_view(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        employee.delete()
        return redirect('employees_list')
    return redirect('employees_list')

@login_required
def daily_cash_entry(request):
    customers = Customer.objects.all()
    loan_details = []
    employees = Employee.objects.all()

    for customer in customers:
        latest_loan_detail = LoanDetail.objects.filter(customer=customer, date=date.today()).first()
        if latest_loan_detail:
            loan_details.append(latest_loan_detail)

    paginator = Paginator(loan_details, 2)  # Show 2 loan details per page.
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'financeapp/daily_cash_entry.html',{
        'loan_details': loan_details,
        'employees': employees,
        'page_obj': page_obj
    })

def update_paid_amount(request):
    num_days = 1
    if request.method == 'POST':
        loan_details = request.POST.getlist('loan_details[]')
        for detail in loan_details:
            loan_detail_id, paid_amount, employee_id = detail.split(',')
            if not paid_amount:
                return JsonResponse({'success': False, 'message': 'Please update all the entries'})

        loan_detail_id = request.POST.get('loan_detail_id')
        paid_amount = request.POST.get('paid_amount')
        employee_id = request.POST.get('employee_id')

        loan_detail = get_object_or_404(LoanDetail, id=loan_detail_id)
        loan_detail.paid_amount = Decimal(paid_amount)
        loan_detail.employee_id = employee_id
        loan_detail.picked_date = date.today()

        if loan_detail.paid_amount > loan_detail.opening_outstand:
            return JsonResponse({'success': False, 'message': 'Invalid request'})
        loan_detail.outstanding_amount = loan_detail.opening_outstand - loan_detail.paid_amount
        loan_detail.balance_amount = loan_detail.daily_collection_amount - loan_detail.paid_amount
        loan_detail.closing_outstand = loan_detail.opening_outstand - loan_detail.paid_amount
        if loan_detail.paid_amount:
            loan_detail.status_paid_unpaid = 'Paid ({})'.format(loan_detail.paid_amount)
        else:
            loan_detail.status_paid_unpaid = 'Unpaid'
        loan_detail.save()

        # Update the next day's opening outstand
        if loan_detail.balance_amount < 0:
            num_days = abs(loan_detail.balance_amount // loan_detail.dea)
            for i in range(int(num_days)):
                next_day_loan_detail = LoanDetail.objects.filter(
                    customer=loan_detail.customer, sr_no=loan_detail.sr_no + (i+1)
                ).first()
                if next_day_loan_detail:
                    next_day_loan_detail.opening_outstand = loan_detail.outstanding_amount
                    next_day_loan_detail.daily_collection_amount = 0
                    next_day_loan_detail.closing_outstand = loan_detail.closing_outstand
                    next_day_loan_detail.status_paid_unpaid = 'Paid on {}'.format(loan_detail.date)
                    next_day_loan_detail.balance_amount = loan_detail.balance_amount + (i+1)*loan_detail.dea
                    next_day_loan_detail.save()

        if loan_detail.paid_amount == loan_detail.dea:
            next_day_loan_detail = LoanDetail.objects.filter(
                customer=loan_detail.customer, sr_no=loan_detail.sr_no + 1
            ).first()
            if next_day_loan_detail:
                next_day_loan_detail.opening_outstand = loan_detail.outstanding_amount
                next_day_loan_detail.save()

        if not loan_detail.paid_amount:
            next_day_loan_detail = LoanDetail.objects.filter(
                customer=loan_detail.customer, sr_no=loan_detail.sr_no + 1
            ).first()
            if next_day_loan_detail:
                next_day_loan_detail.opening_outstand = loan_detail.outstanding_amount
                next_day_loan_detail.daily_collection_amount = loan_detail.balance_amount + loan_detail.dea
                next_day_loan_detail.save()

        updated_data = {
            'paid_amount': str(loan_detail.paid_amount),
            'outstanding_amount': str(loan_detail.outstanding_amount),
            'balance_amount': str(loan_detail.balance_amount)
        }

        return JsonResponse({'success': True, 'message': 'Paid amount updated successfully!', 'updated_data': updated_data})

    return JsonResponse({'success': False, 'message': 'Invalid request'})

def generate_csv_npa(request):
    sum_loan_amount = 0
    sum_opening_outstand = 0
    sum_daily_collection_amount = 0
    sum_paid_amount = 0
    sum_outstanding_amount = 0

    loan_details = LoanDetail.objects.all().order_by('-date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=daily_npa_list_{}.csv'.format(date.today())

    writer = csv.writer(response)
    writer.writerow([
        'SR No', 'Date', 'Phone Number', 'Name', 'Customer Number', 'Loan Amount',
        'Outstanding Amount'
    ])
    count = 1
    for detail in loan_details:
        if detail.date == date.today() and not detail.paid_amount and detail.daily_collection_amount:
            sum_loan_amount += detail.customer.loan_amount
            sum_opening_outstand += detail.opening_outstand
            sum_daily_collection_amount += detail.daily_collection_amount
            sum_paid_amount += detail.paid_amount
            sum_outstanding_amount += detail.closing_outstand

            writer.writerow([
                detail.sr_no,
                detail.date,
                detail.customer.phone_number,
                f"{detail.customer.first_name} {detail.customer.last_name}",
                detail.customer.customer_number,
                detail.customer.loan_amount,
                detail.closing_outstand,
            ])
            count += 1

    writer.writerow([' ', detail.date, ' ', ' ', ' ', sum_loan_amount, sum_outstanding_amount])

    return response

def generate_daily_csv(request):
    sum_loan_amount = 0
    sum_opening_outstand = 0
    sum_daily_collection_amount = 0
    sum_paid_amount = 0
    sum_outstanding_amount = 0

    loan_details = LoanDetail.objects.all().order_by('-date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=daily_cash_entry_{}.csv'.format(date.today())

    writer = csv.writer(response)
    writer.writerow([
        'SR No', 'Date', 'Phone Number', 'Name', 'Customer Number', 'Loan Amount',
        'Outstanding Amount (All)', 'DEA (Per Day EMI)', ' Daily Collection Amount', 'Paid Amount', 'Picked By (Employee)', 'Outstanding Amount', 'Balance Amount'
    ])  
    count=1
    for detail in loan_details:
        if detail.date != date.today():
            continue
        if not detail.daily_collection_amount:
            continue
        sum_loan_amount += detail.customer.loan_amount
        sum_opening_outstand += detail.opening_outstand
        sum_daily_collection_amount += detail.daily_collection_amount
        sum_paid_amount += detail.paid_amount
        sum_outstanding_amount += detail.closing_outstand
        
        employee_name = ""

        if detail.employee is not None:
            employee_name = f"{detail.employee.first_name} {detail.employee.last_name}" 
        writer.writerow([
            count,
            detail.date,
            detail.customer.phone_number,
            f"{detail.customer.first_name} {detail.customer.last_name}",
            detail.customer.customer_number,
            detail.customer.loan_amount,
            detail.opening_outstand,
            detail.dea,
            detail.daily_collection_amount,
            detail.paid_amount,
            employee_name,
            detail.closing_outstand,
            detail.balance_amount
        ])
        count += 1

    writer.writerow([' ', detail.date, ' ', ' ', ' ', sum_loan_amount, sum_opening_outstand, '', sum_daily_collection_amount,
                     sum_paid_amount, ' ', sum_outstanding_amount, ''])

    return response

@login_required
def customers_update_data_view(request):
    selected_date = request.GET.get('selected_date')
    customers = []
    active_loans_count = 0

    if selected_date:
        try:
            selected_date = datetime.datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            try:
                selected_date = datetime.datetime.strptime(selected_date, "%B %d, %Y").date()
            except ValueError:
                selected_date = None

        if selected_date:
            loan_details = LoanDetail.objects.filter(date=selected_date, closing_outstand__gt=0)
            customers = set(loan.customer for loan in loan_details)
            active_loans_count = loan_details.count()

            for customer in customers:
                latest_loan_detail = LoanDetail.objects.filter(customer=customer).order_by('-date').first()
                if latest_loan_detail:
                    customer.balance_due = latest_loan_detail.closing_outstand
                    customer.save()

    # Pagination
    paginator = Paginator(list(customers), 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'customers': page_obj, 
        'selected_date': selected_date,
        'active_loans_count': active_loans_count,
        'page_obj': page_obj,
    }
    return render(request, 'financeapp/customers_update_data.html', context)

@login_required
def export_csv_view(request):
    selected_date = request.GET.get('selected_date')
    customers = []
    active_loans_count = 0

    if selected_date:
        # Convert selected_date to a date object
        selected_date = datetime.datetime.strptime(selected_date, "%Y-%m-%d").date()

        # Get all customers with active loans on the selected date
        loan_details = LoanDetail.objects.filter(date=selected_date, closing_outstand__gt=0)
        customers = set(loan.customer for loan in loan_details)
        active_loans_count = loan_details.count()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="active_loans_{selected_date}.csv"'

    writer = csv.writer(response)
    writer.writerow(['SR No.', 'Customer Number', 'Customer Name', 'Customer Phone Number', 'EMI', 'Closing Date', 'EMI Due', 'Balance Due'])

    for idx, customer in enumerate(customers, start=1):
        latest_loan_detail = LoanDetail.objects.filter(customer=customer).order_by('-date').first()
        balance_due = latest_loan_detail.closing_outstand if latest_loan_detail else 'N/A'
        writer.writerow([
            idx,
            customer.customer_number,
            f"{customer.first_name} {customer.last_name}",
            customer.phone_number,
            customer.per_day_emi,
            customer.closing_date,
            customer.emi_due,
            balance_due
        ])

    return response

@login_required
def assign_employee_view(request):
    customers = Customer.objects.all()
    employees = Employee.objects.all()
    
    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        employee_id = request.POST.get('employee_id')
        customer = Customer.objects.get(id=customer_id)
        employee = Employee.objects.get(id=employee_id)
        
        # Create or update assignment for today
        assignment, created = EmployeeAssignment.objects.update_or_create(
            customer=customer,
            date_assigned=date.today(),
            defaults={'employee': employee}
        )
        
        return redirect('assign_employee')

    context = {
        'customers': customers,
        'employees': employees,
    }
    
    return render(request, 'financeapp/assign_employee.html', context)



@login_required
def customers_payment_history_view(request):
    customer_number = request.GET.get('customer_number')
    phone_number = request.GET.get('phone_number')
    customer = None
    payments = []

    if customer_number and phone_number:
        customer = Customer.objects.filter(customer_number=customer_number, phone_number=phone_number).first()
        if customer:
            payments = LoanDetail.objects.filter(customer=customer).order_by('date')

    # Pagination
    paginator = Paginator(payments, 10)  # Show 10 payments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_received = sum(payment.paid_amount for payment in payments)
    total_outstanding_amount = sum(payment.outstanding_amount for payment in payments)

    context = {
        'customer': customer,
        'payments': page_obj,  # Pass the paginated object to the template
        'total_received': total_received,
        'total_outstanding_amount': total_outstanding_amount,
        'page_obj': page_obj,  # Pass the page object to handle pagination in the template
    }
    return render(request, 'financeapp/customers_payment_history.html', context)

@login_required
def export_customer_payment_history_csv(request):
    customer_number = request.GET.get('customer_number')
    phone_number = request.GET.get('phone_number')
    customer = None
    payments = []

    if customer_number and phone_number:
        customer = Customer.objects.filter(customer_number=customer_number, phone_number=phone_number).first()
        if customer:
            payments = LoanDetail.objects.filter(customer=customer).order_by('date')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={customer.customer_number}_payment_history.csv'

    writer = csv.writer(response)
    writer.writerow(['SR No.', 'EMI Date', 'Amount Received', 'Outstanding Amount'])

    for index, payment in enumerate(payments, start=1):
        writer.writerow([index, payment.date, payment.paid_amount, payment.outstanding_amount])

    writer.writerow([])
    writer.writerow(['Loan Amount', customer.loan_amount, ' '])
    writer.writerow(['Total Received Amount', sum(payment.paid_amount for payment in payments), ' '])
    writer.writerow(['Total Pending Amount', customer.loan_amount - sum(payment.paid_amount for payment in payments)])

    return response


@login_required
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        form = CustomerEditForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('customers_list')
    else:
        form = CustomerEditForm(instance=customer)
    return render(request, 'financeapp/edit_customer.html', {'form': form, 'customer': customer})

@login_required
def delete_customer(request, id):
    customer = get_object_or_404(Customer, id=id)
    if request.method == 'POST':
        customer.delete()
        return redirect('customers_list')
    return render(request, 'confirm_delete.html', {'customer': customer})

@login_required
def employee_dashboard(request):
    # Your employee dashboard logic here
    return render(request, 'financeapp/employee_dashboard.html')

@login_required
def daily_cash_view(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date and end_date:
        loan_details = LoanDetail.objects.filter(date__range=[start_date, end_date])
    else:
        loan_details = LoanDetail.objects.all()

    total_cash = loan_details.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
    daily_amount = loan_details.values('date').annotate(dsum=Sum('paid_amount')).order_by('date')

    # Pagination
    paginator = Paginator(daily_amount, 4)  # Show 10 entries per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'loan_details': loan_details,
        'total_cash': total_cash,
        'daily_amount': page_obj,  # Pass the paginated object to the template
        'page_obj': page_obj,  # Pass the page object to handle pagination in the template
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'financeapp/daily_cash.html', context)

def download_daily_cash_report(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date and end_date:
        loan_details = LoanDetail.objects.filter(date__range=[start_date, end_date])
    else:
        loan_details = LoanDetail.objects.all()

    daily_amount = loan_details.values('date').annotate(dsum=Sum('paid_amount')).order_by('date')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=daily_cash_report_{}_to_{}.csv'.format(start_date, end_date)

    writer = csv.writer(response)
    writer.writerow(['Date', 'Daily Collection Amount'])

    total_amount = 0
    for amount in daily_amount:
        total_amount += amount['dsum']
        writer.writerow([amount['date'], amount['dsum']])
    writer.writerow(['Total Amount', total_amount])
    return response

@login_required
def daily_transactions(request):
    today = date.today()
    daily_transaction, created = DailyTransaction.objects.get_or_create(date=today)
    daily_transaction.opening_balance = DailyTransaction.objects.filter(date=today - timedelta(days=1)).first().closing_balance or 0
    daily_transaction.daily_collection = LoanDetail.objects.filter(date=today).aggregate(total=Sum('paid_amount'))['total'] or 0
    daily_transaction.loan_distribution = Customer.objects.filter(opening_date=today).aggregate(total=Sum('loan_amount'))['total'] or 0
    daily_transaction.save()
    
    if request.method == 'POST':
        form = DailyTransactionForm(request.POST)
        if form.is_valid():
            daily_transaction, created = DailyTransaction.objects.get_or_create(date=today)
            
            # Update the existing entry
            daily_transaction.add_cash += form.cleaned_data['add_cash']
            daily_transaction.expenses += form.cleaned_data['expenses']
            
            # Fetch and calculate data            
            daily_transaction.save()
            return redirect('daily_transactions')
    else:
        form = DailyTransactionForm()
    daily_transactions = DailyTransaction.objects.all().order_by('-date')
    paginator = Paginator(daily_transactions, 5)  # Show 10 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'financeapp/daily_transactions.html', {
        'form': form, 
        'daily_transactions': daily_transactions, 
        'page_obj': page_obj
        })

def download_transactions_csv(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    transactions = DailyTransaction.objects.filter(date__range=[start_date, end_date])

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="daily_transactions_{start_date}_to_{end_date}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Opening Balance', 'Daily Collection', 'Loan Distribution', 'Add Cash', 'Expenses', 'Closing Balance'])

    for transaction in transactions:
        writer.writerow([
            transaction.date,
            transaction.opening_balance,
            transaction.daily_collection,
            transaction.loan_distribution,
            transaction.add_cash,
            transaction.expenses,
            transaction.closing_balance
        ])

    return response

def update_unfilled_prevday():
    today = date.today()
    prev_day = today - timedelta(days=1)

    unfilled_loans = LoanDetail.objects.filter(date=prev_day, status_paid_unpaid='')

    for loan in unfilled_loans:
        loan.status_paid_unpaid = 'Unpaid'
        loan.balance_amount += loan.daily_collection_amount
        loan.closing_outstand = loan.opening_outstand
        loan.save()

        # Update today's opening outstanding and daily collection amount for the customer
        customer = loan.customer
        today_loan_detail = LoanDetail.objects.get(customer=customer, date=today)

        today_loan_detail.opening_outstand = loan.closing_outstand
        today_loan_detail.daily_collection_amount += loan.balance_amount
        today_loan_detail.save()
        
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user_type = form.cleaned_data['user_type']

            if user_type == 'admin':
                user = authenticate(request, username=email, password=password)
                if user is not None and user.groups.filter(name='Admin').exists():
                    update_unfilled_prevday()
                    login(request, user)
                    return redirect('dashboard')
                else:
                    form.add_error(None, 'Invalid email or password for admin.')
            
            elif user_type == 'employee':
                try:
                    employee = Employee.objects.get(email=email, password=password)
                    # session handling for employees
                    request.session['employee_id'] = employee.id
                    update_unfilled_prevday()
                    return redirect('dashboard')
                except Employee.DoesNotExist:
                    form.add_error(None, 'Invalid email or password for employee.')
    else:
        form = LoginForm()
    return render(request, 'financeapp/login.html', {'form': form})