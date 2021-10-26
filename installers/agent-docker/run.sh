docker run \
       -dit --name siteagent \
       -v $(pwd)/conf/etc/dtnrm.yaml:/etc/dtnrm.yaml \
       -v $(pwd)/conf/etc/grid-security/hostcert.pem:/etc/grid-security/hostcert.pem \
       -v $(pwd)/conf/etc/grid-security/hostkey.pem:/etc/grid-security/hostkey.pem \
       -v $(pwd)/conf/opt/config/:/opt/config/ \
       --cap-add=NET_ADMIN \
       --net=host \
       --log-opt max-size=10m --log-opt max-file=10 \
       siteagent
