# Generated by Django 4.1.6 on 2024-07-09 07:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financeapp', '0012_alter_customer_opening_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='customer_number',
            field=models.CharField(default='', max_length=20),
        ),
    ]
