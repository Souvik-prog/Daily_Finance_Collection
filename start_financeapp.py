import os
import webbrowser
import subprocess
import time

def start_django():
    # Change to your Django project directory
    os.chdir("E:\Daily_Finance_Collection\daily_finance_collection")

    # Start the Django development server
    subprocess.Popen(['python', 'manage.py', 'runserver'])

    # Wait for a few seconds to allow the server to start
    time.sleep(5)

    # Open the Django application in the default web browser
    webbrowser.open('http://127.0.0.1:8000/login')

if __name__ == "__main__":
    start_django()

# pip install pyinstaller
# pyinstaller --onefile start_financeapp.py