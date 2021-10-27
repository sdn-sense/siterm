FROM centos:8

ARG GITREPO=siterm
ARG GITORG=sdn-sense
ARG GITBR=master

MAINTAINER Justas Balcas <jbalcas@caltech.edu>

RUN mkdir -p /opt/ && mkdir -p /opt/{config,dtnrmcode}
RUN yum -y install git sudo

RUN cd /opt/dtnrmcode && git clone -b $GITBR https://github.com/$GITORG/$GITREPO
RUN cd /opt/dtnrmcode/$GITREPO/installers/ && sudo sh ./fresh-siterm-agent-install.sh -R /opt/ -D yes -G $GITREPO  -O $GITORG -B $GITBR

RUN rpm -i https://repo.opensciencegrid.org/osg/3.5/el8/release/x86_64/osg-ca-certs-1.100-1.osg35.el8.noarch.rpm

COPY run-wrapper.sh /usr/local/bin/run-wrapper.sh
CMD /usr/local/bin/run-wrapper.sh
