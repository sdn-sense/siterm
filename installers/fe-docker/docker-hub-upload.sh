#!/bin/bash

TAG=dev

docker login
dockerimageid=`docker images | grep sitefe | grep latest | awk '{print $3}'`
docker tag $dockerimageid sdnsense/site-rm-sense:$TAG
docker push sdnsense/site-rm-sense:$TAG
