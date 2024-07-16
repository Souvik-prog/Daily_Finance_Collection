"""daily_finance_collection URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
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
from financeapp.views import login_view
from django.urls import path
from financeapp.views import (
    login_view, dashboard_view, add_customer_view, 
    add_employee_view, customers_list_view, employees_list_view,
    daily_cash_view, customers_update_data_view, customers_payment_history_view,
    edit_customer, delete_customer, delete_employee_view, edit_employee_view, employee_dashboard, daily_cash_view,
    export_csv_view, export_customer_payment_history_csv, assign_employee_view,
    daily_cash_entry, generate_excel, generate_daily_csv, update_paid_amount, generate_csv_npa, 
    download_daily_cash_report, daily_transactions, download_transactions_csv, 
    google_callback, google_login, data_backup, backup_to_drive
    )
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('employee_dashboard/', employee_dashboard, name='employee_dashboard'),
    path('add-customer/', add_customer_view, name='add_customer'),
    path('customers-list/', customers_list_view, name='customers_list'),
    path('add_employee/', add_employee_view, name='add_employee'),
    path('employees_list/', employees_list_view, name='employees_list'),
    path('edit_employee/<int:pk>/', edit_employee_view, name='edit_employee'),
    path('delete_employee/<int:pk>/', delete_employee_view, name='delete_employee'),
    path('daily_cash/', daily_cash_view, name='daily_cash'),
    path('customers_update_data/', customers_update_data_view, name='customers_update_data'),
    path('export_csv/', export_csv_view, name='export_csv'),
    path('customers_payment_history/', customers_payment_history_view, name='customers_payment_history'),
    path('export_customer_payment_history_csv/', export_customer_payment_history_csv, name='export_customer_payment_history_csv'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('customers/edit/<int:customer_id>/', edit_customer, name='edit_customer'),
    path('delete_customer/<int:id>/', delete_customer, name='delete_customer'),
    path('assign-employee/', assign_employee_view, name='assign_employee'),
    path('daily-cash-entry/', daily_cash_entry, name='daily_cash_entry'),
    path('update_paid_amount/', update_paid_amount, name='update_paid_amount'),
    path('generate-daily-csv/', generate_daily_csv, name='generate_daily_csv'),
    path('generate-csv-npa/', generate_csv_npa, name='generate_csv_npa'),
    path('generate-excel/<int:customer_id>/', generate_excel, name='generate_excel'),
    path('download_daily_cash_report/', download_daily_cash_report, name='download_daily_cash_report'),
    path('daily-transactions/', daily_transactions, name='daily_transactions'),
    path('download-transactions-csv/', download_transactions_csv, name='download_transactions_csv'),
    path('google-login/', google_login, name='google_login'),
    path('google-callback/', google_callback, name='google_callback'),
    path('data-backup/', data_backup, name='data_backup'),
    path('backup-to-drive/<int:account_id>/', backup_to_drive, name='backup_to_drive'),
]
