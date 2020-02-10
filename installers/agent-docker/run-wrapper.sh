#!/bin/bash

rm -f log.out
# Log everything in the log file
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>log.out 2>&1

set -x
set -m
chown -R apache:apache  /opt/siterm/config/
# Start the first process
sudo -u root /usr/bin/dtnrmagent-update start
status=$?
exit_code=0
if [ $status -ne 0 ]; then
  echo "Failed to start dtnrmagent-update: $status"
  exit_code=1
fi
sleep 5
# Start the second process
sudo -u root /usr/bin/dtnrm-ruler start
status=$?
if [ $status -ne 0 ]; then
  echo "Failed to start dtnrm-ruler: $status"
  exit_code=2
fi
# Naive check runs checks once a minute to see if either of the processes exited.
# This illustrates part of the heavy lifting you need to do if you want to run
# more than one service in a container. The container exits with an error
# if it detects that either of the processes has exited.
# Otherwise it loops forever, waking up every 60 seconds

while sleep 10; do
  ps aux |grep dtnrmagent-update |grep -q -v grep
  PROCESS_1_STATUS=$?
  ps aux |grep dtnrm-ruler |grep -q -v grep
  PROCESS_2_STATUS=$?
  # If the greps above find anything, they exit with 0 status
  # If they are not both 0, then something is wrong
  if [ $PROCESS_1_STATUS -ne 0 -o $PROCESS_2_STATUS -ne 0 ]; then
    echo "One of the processes has already exited."
    echo "dtnrmagent-update: " $PROCESS_1_STATUS
    echo "dtnrm-ruler:" $PROCESS_2_STATUS
    exit_code=5
    break;
  fi
done
echo "We just got break. Endlessly sleep for debugging purpose."
while true; do sleep 1; done
