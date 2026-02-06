#!/bin/bash

set -e

# TODO: Fix ENV does not load from .env file issue
# Wait until PostgreSQL is ready
echo "Waiting for PostgreSQL to be ready..."
while ! nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
  sleep 1
done
echo "PostgreSQL is ready!"

# Wait until Redis is ready
echo "Waiting for Redis to be ready..."
if  [ -n "${REDIS_HOST}" ] && [ -n "${REDIS_PORT}" ]; then
  while ! nc -z ${REDIS_HOST} ${REDIS_PORT}; do
    echo "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
    sleep 1
  done
fi

# Apply Django migrations
echo "Applying Django migrations..."
python manage.py migrate --noinput
echo "Migrations applied."

# Create superuser if specified
if [ "$CREATE_SUPERUSER" = "true" ]; then
   echo "Creating superuser..."
   python manage.py shell -c "
from apps.users.models import User
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME:-admin}').exists():
   User.objects.create_superuser(
       username='${DJANGO_SUPERUSER_USERNAME:-admin}',
       email='${DJANGO_SUPERUSER_EMAIL:-admin@example.com}',
       password='${DJANGO_SUPERUSER_PASSWORD:-admin123}'
   )
   print('Superuser created!')
else:
   print('Superuser already exists')
" 2>/dev/null || echo "Note: Superuser creation skipped or failed"
fi

# Populate DB with dummy data if specified
if [ "$POPULATE_DUMMY_DATA" = "true" ]; then
    echo "Populating database with dummy data..."
    python manage.py populate_db
    echo "Dummy data populated."
fi


# Execute the command passed to the entrypoint
echo "========================================"
echo "Starting the application..."
echo "========================================"
if [ "$ENVIRONMENT" = "production" ]; then
 gunicorn config.wsgi:application \
   --bind 0.0.0.0:${PORT:-8000} \
   --workers 3 \
   --threads 2 \
   --capture-output
else
 python manage.py runserver 0.0.0.0:${PORT:-8000}
fi



