@echo off
setlocal

IF "%1"=="--reset" (
    echo Resetting project...

    if exist "address\migrations" rmdir /s /q "address\migrations"
    if exist "job\migrations" rmdir /s /q "job\migrations"
    if exist "professional\migrations" rmdir /s /q "professional\migrations"
    if exist "service\migrations" rmdir /s /q "service\migrations"
    if exist "user\migrations" rmdir /s /q "user\migrations"

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

    if exist db.sqlite3 (
        del db.sqlite3
    )
    if exist .venv (
        rmdir /s /q .venv
    )
    python -m venv .venv

    call .venv\Scripts\activate.bat

    python -m pip install --upgrade pip
    pip install -r requirements.txt

    python manage.py makemigrations service
    python manage.py makemigrations address
    python manage.py makemigrations user
    python manage.py makemigrations professional
    python manage.py makemigrations job

    python manage.py migrate

    python loaddata.py

    python manage.py shell -c "from user.models import CustomUser; CustomUser.objects.create_superuser('admin@gmail.com', '123')"
    goto :eof
)

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt

echo Done.
echo Done.
echo Done.
