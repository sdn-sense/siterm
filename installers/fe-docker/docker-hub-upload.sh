#!/bin/bash

docker login
dockerimageid=`docker images | grep sitefe | grep latest | awk '{print $3}'`
docker tag $dockerimageid sdnsense/site-rm-sense:latest
docker push sdnsense/site-rm-sense
