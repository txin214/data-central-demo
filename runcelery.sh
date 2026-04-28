#!/bin/sh
cd /Users/bill/Projects/DC1/AllenKit-dc
source venv/bin/activate && python -m celery -A allenkit1 worker -l info

