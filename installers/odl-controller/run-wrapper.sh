#!/bin/bash

rm -f log.out
# Log everything in the log file
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>log.out 2>&1

set -x
set -m

/opt/karaf/bin/start
# Features are not installed by default and not installed inside the docker build.
# We do this here once karaf is running. You might consider modify features what you need.
# It needs to sleep few seconds to make sure karaf is up before installing.
sleep 15
/opt/karaf/bin/client 'feature:install odl-dluxapps-applications odl-restconf odl-l2switch-all odl-mdsal-apidocs odl-dlux-core'

while true; do sleep 120; done
