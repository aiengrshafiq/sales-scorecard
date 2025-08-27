#!/bin/sh
set -e

# This script checks an environment variable to decide what to run.
# If APP_MODE is "api", it runs the web server.
# If APP_MODE is "worker", it runs the Celery worker.

if [ "$APP_MODE" = "api" ]; then
  echo "Starting in API mode..."
  exec uvicorn main:app --host 0.0.0.0 --port 80
elif [ "$APP_MODE" = "worker" ]; then
  echo "Starting in Worker mode..."
  exec celery -A celery_worker worker -P gevent --loglevel=INFO
else
  echo "Error: APP_MODE environment variable not set or invalid (must be 'api' or 'worker')."
  exit 1
fi