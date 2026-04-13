#!/bin/sh
source venv/bin/activate && python -m celery -A allenkit1 worker -l info

