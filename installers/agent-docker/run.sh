docker run \
       -dit --name site-agent-sense \
       -v $(pwd)/conf/etc/dtnrm/main.conf:/etc/dtnrm/main.conf \
       -v $(pwd)/conf/etc/grid-security/hostcert.pem:/etc/grid-security/hostcert.pem \
       -v $(pwd)/conf/etc/grid-security/hostkey.pem:/etc/grid-security/hostkey.pem \
       -v $(pwd)/conf/opt/config/:/opt/config/ \
       --cap-add=NET_ADMIN \
       --net=host \
       siteagent
