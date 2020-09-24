FROM ubuntu:18.04

MAINTAINER Justas Balcas <jbalcas@caltech.edu>

# Magnesium 0.12.0
# Sodium    0.11.2
# Neon      0.10.3
# Fluorine  0.9.3
# Oxygen    0.8.4
ENV ODLRELEASE 0.12.0


RUN apt-get update && apt-get install -y --no-install-recommends \
    curl iproute2 iputils-ping mininet net-tools wget vlan \
    tcpdump vim openjdk-11-jdk openvswitch-switch

RUN cd /opt/ && wget http://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/karaf/$ODLRELEASE/karaf-$ODLRELEASE.tar.gz
RUN cd /opt/ && tar -xvzf karaf-$ODLRELEASE.tar.gz
RUN cd /opt/ && mv karaf-$ODLRELEASE karaf

EXPOSE 6633 6653 8181
COPY run-wrapper.sh /usr/local/bin/run-wrapper.sh
CMD /usr/local/bin/run-wrapper.sh
