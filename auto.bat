@echo off
setlocal

REM Check for --reset argument
IF "%1"=="--reset" (
    echo Resetting project...
    REM Remove migrations folders ONLY from project apps
    if exist "address\migrations" rmdir /s /q "address\migrations"
    if exist "job\migrations" rmdir /s /q "job\migrations"
    if exist "professional\migrations" rmdir /s /q "professional\migrations"
    if exist "service\migrations" rmdir /s /q "service\migrations"
    if exist "user\migrations" rmdir /s /q "user\migrations"
    REM Recreate migrations folders with __init__.py
    mkdir "address\migrations"
    type nul > "address\migrations\__init__.py"
    mkdir "job\migrations"
    type nul > "job\migrations\__init__.py"
    mkdir "professional\migrations"
    type nul > "professional\migrations\__init__.py"
    mkdir "service\migrations"
    type nul > "service\migrations\__init__.py"
    mkdir "user\migrations"
    type nul > "user\migrations\__init__.py"
    REM Remove db.sqlite3
    if exist db.sqlite3 (
        del db.sqlite3
    )
    REM Remove and recreate .venv to fix corrupted Django install
    if exist .venv (
        rmdir /s /q .venv
    )
    python -m venv .venv
    REM Activate venv
    call .venv\Scripts\activate.bat
    REM Install packages from requirements.txt
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    REM Run makemigrations for each app in each line
    python manage.py makemigrations service
    python manage.py makemigrations address
    python manage.py makemigrations user
    python manage.py makemigrations professional
    python manage.py makemigrations job
    REM Run migrate
    python manage.py migrate
    REM Load data using loaddata.py
    python loaddata.py
    REM Create superuser
    python manage.py shell -c "from user.models import CustomUser; CustomUser.objects.create_superuser('admin@gmail.com', '123')"
    goto :eof
)

REM Create .venv if it does not exist
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Install packages from requirements.txt (only missing ones)
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Done.
echo Done.
echo Done.
