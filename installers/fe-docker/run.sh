docker run \
       -dit --name site-fe-sense \
       -v $(pwd)/conf/etc/dtnrm.yaml:/etc/dtnrm.yaml \
       -v $(pwd)/conf/etc/httpd/conf.d/sitefe-httpd.conf:/etc/httpd/conf.d/sitefe-httpd.conf \
       -v $(pwd)/conf/etc/httpd/conf.d/welcome.conf:/etc/httpd/conf.d/welcome.conf \
       -v $(pwd)/conf/etc/httpd/conf.d/ssl.conf:/etc/httpd/conf.d/ssl.conf \
       -v $(pwd)/conf/etc/httpd/certs/cert.pem:/etc/httpd/certs/cert.pem \
       -v $(pwd)/conf/etc/httpd/certs/privkey.pem:/etc/httpd/certs/privkey.pem \
       -v $(pwd)/conf/etc/httpd/certs/fullchain.pem:/etc/httpd/certs/fullchain.pem \
       -v $(pwd)/conf/etc/grid-security/hostcert.pem:/etc/grid-security/hostcert.pem \
       -v $(pwd)/conf/etc/grid-security/hostkey.pem:/etc/grid-security/hostkey.pem \
       -v $(pwd)/conf/opt/config/:/opt/config/ \
       -p 8080:80 \
       -p 8443:443 \
       sitefe
