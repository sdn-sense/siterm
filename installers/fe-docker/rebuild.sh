#!/bin/bash

dockerid=`docker ps -a | grep sitefe | awk '{print $1}'`
docker stop $dockerid
docker rm $dockerid

docker build  --no-cache -t sitefe .
echo "IF BUILD SUCCESSFUL. START IT WITH ./run.sh"
