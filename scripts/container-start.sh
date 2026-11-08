#!/bin/sh
# Schema creation is an explicit deployment task, not an action on every request.
set -eu
exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers "${WEB_CONCURRENCY:-2}" --threads 4 --timeout 30 'movie_court:create_app()'
