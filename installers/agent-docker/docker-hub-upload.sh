#!/bin/bash

docker login
dockerimageid=`docker images | grep siteagent | grep latest | awk '{print $3}'`
docker tag $dockerimageid sdnsense/site-agent-sense:latest
docker push sdnsense/site-agent-sense
