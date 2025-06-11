#!/bin/bash

# Exit on any error
set -e

echo "Starting Speakle application..."

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z db 5432; do
  echo "Database is unavailable - sleeping"
  sleep 1
done
echo "Database is up - continuing..."

# Wait for Redis to be ready
echo "Waiting for Redis..."
while ! nc -z redis 6379; do
  echo "Redis is unavailable - sleeping"
  sleep 1
done
echo "Redis is up - continuing..."

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
echo "Creating superuser if not exists..."
python manage.py shell << END
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@speakle.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superuser {username} created successfully')
else:
    print(f'Superuser {username} already exists')
END

echo "Starting application..."
exec "$@" 