#!/bin/sh
# macos:
# launch the redis and celery scripts to run our django app locally

cd /Users/bill/Projects/DC1/AllenKit-dc
osascript -e "tell application \"Terminal\" to do script \"/Users/bill/Projects/DC1/AllenKit-dc/runredis.sh\""
osascript -e "tell application \"Terminal\" to do script \"/Users/bill/Projects/DC1/AllenKit-dc/runcelery.sh\""

