docker run \
       -dit --name senseodl \
       -p 6633:6633 \
       -p 6653:6653 \
       -p 8181:8181 \
       --privileged \
       -v /lib/modules:/lib/modules \
       sense-odl
