set -e

if [[ "$1" == "--reset" ]]; then
    echo "Resetting project..."
    rm -rf address/migrations job/migrations professional/migrations service/migrations user/migrations

    mkdir -p address/migrations job/migrations professional/migrations service/migrations user/migrations
    touch address/migrations/__init__.py
    touch job/migrations/__init__.py
    touch professional/migrations/__init__.py
    touch service/migrations/__init__.py
    touch user/migrations/__init__.py

    rm -f db.sqlite3

    rm -rf .venv
    python3 -m venv .venv

    source .venv/bin/activate

    python -m pip install --upgrade pip
    pip install -r requirements.txt

    python manage.py makemigrations service
    python manage.py makemigrations address
    python manage.py makemigrations user
    python manage.py makemigrations professional
    python manage.py makemigrations job
    python manage.py makemigrations subscription
    python manage.py makemigrations inventory
    python manage.py makemigrations project_management
    python manage.py makemigrations project_settings

    python manage.py migrate

    python loaddata.py

    python manage.py shell -c "from user.models import CustomUser; CustomUser.objects.create_superuser('admin@gmail.com', '123')"
    exit 0
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Done."
echo "Done."
echo "Done."
