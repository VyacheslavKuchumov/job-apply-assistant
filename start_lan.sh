#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
python manage.py migrate --noinput
exec python manage.py runserver 0.0.0.0:8000
