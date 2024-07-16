from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group

class Command(BaseCommand):
    help = 'Create employee users'

    def handle(self, *args, **kwargs):
        employee_group, created = Group.objects.get_or_create(name='Employee')

        employees = [
            {'username': 'Souvik', 'email': 'gsouvik407@gmail.com', 'password': '12345'},
            {'username': 'Srijon', 'email': 'srijan123@gmail.com', 'password': '123456'},
            # Add more employees as needed
        ]

        for emp in employees:
            user, created = User.objects.get_or_create(username=emp['username'], email=emp['email'])
            if created:
                user.set_password(emp['password'])
                user.save()
                user.groups.add(employee_group)
                self.stdout.write(self.style.SUCCESS(f'Successfully created user {emp["username"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'User {emp["username"]} already exists'))

# Run this command with:
# python manage.py create_employees
