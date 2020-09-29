#!/bin/bash

rm -f log.out
# Log everything in the log file
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>log.out 2>&1

set -x
set -m

# Remove yaml files to prefetch from scratch;
rm -f /tmp/*-mapping.yaml
rm -f /tmp/*-FE-main.yaml
rm -f /tmp/*-FE-auth.yaml
# Remove any PID files left afer reboot/stop.
rm -f /tmp/dtnrm*.pid

# As first run, Run Custom CA prefetch and add them to CAs dir.
sh /etc/cron-scripts/siterm-ca-cron.sh

datadir=/opt/config/
echo "1. Making apache as owner of $datadir"
chown apache:apache -R $datadir
# File permissions, recursive
echo "2. Recursive file permissions to 0644 in $datadir"
find $datadir -type f -exec chmod 0644 {} \;
# Dir permissions, recursive
echo "3. Recursive directory permissions to 0755 in $datadir"
find $datadir -type d -exec chmod 0755 {} \;
# TODO:
# Make a script which loops over the config on GIT and prepares
# dirs and database. Now it requires to do it manually or restart docker

# Run crond
touch /var/log/cron.log
/usr/sbin/crond
crontab /etc/cron.d/siterm-crons

# Start the first process
mkdir -p /run/httpd
/usr/sbin/httpd -k restart
status=$?
exit_code=0
if [ $status -ne 0 ]; then
  echo "Failed to start httpd: $status"
  exit_code=1
fi

# Start the second process
sudo -u root /usr/bin/LookUpService-update restart &
status=$?
if [ $status -ne 0 ]; then
  echo "Failed to restart LookUpService-update: $status"
  exit_code=2
fi
sleep 5
# Start the third process
sudo -u root /usr/bin/PolicyService-update restart &
status=$?
if [ $status -ne 0 ]; then
  echo "Failed to restart PolicyService-update: $status"
  exit_code=3
fi
sleep 5
# Start the fourth process
sudo -u root /usr/bin/ProvisioningService-update restart &
status=$?
if [ $status -ne 0 ]; then
  echo "Failed to restart ProvisioningService-update: $status"
  exit_code=4
fi
# Naive check runs checks once a minute to see if either of the processes exited.
# This illustrates part of the heavy lifting you need to do if you want to run
# more than one service in a container. The container exits with an error
# if it detects that either of the processes has exited.
# Otherwise it loops forever, waking up every 60 seconds
sleep 5
echo "Making apache as owner of $datadir"
chown apache:apache -R $datadir

while sleep 30; do
  ps aux |grep httpd |grep -q -v grep
  PROCESS_1_STATUS=$?
  ps aux |grep LookUpService-update |grep -q -v grep
  PROCESS_2_STATUS=$?
  ps aux |grep PolicyService-update |grep -q -v grep
  PROCESS_3_STATUS=$?
  ps aux |grep ProvisioningService-update |grep -q -v grep
  PROCESS_4_STATUS=$?
  # If the greps above find anything, they exit with 0 status
  # If they are not both 0, then something is wrong
  if [ $PROCESS_1_STATUS -ne 0 -o $PROCESS_2_STATUS -ne 0 -o $PROCESS_3_STATUS -ne 0 -o $PROCESS_4_STATUS -ne 0 ]; then
    echo "One of the processes has already exited."
    echo "httpd: " $PROCESS_1_STATUS
    echo "LookUpService-update:" $PROCESS_2_STATUS
    echo "PolicyService-update:" $PROCESS_3_STATUS
    echo "ProvisioningService-update:" $PROCESS_4_STATUS 
    exit_code=5
    break;
  fi
done
echo "We just got break. Endlessly sleep for debugging purpose."
while true; do sleep 120; done
