FROM centos:7

MAINTAINER Justas Balcas <jbalcas@caltech.edu>

ENV GITREPO siterm
ENV GITORG juztas

RUN mkdir -p /opt/ && mkdir -p /opt/{config,dtnrmcode}
RUN  yum -y install git sudo
RUN cd /opt/dtnrmcode && git clone https://github.com/$GITORG/$GITREPO
RUN cd /opt/dtnrmcode/$GITREPO/installers/ && sudo sh ./fresh-siterm-agent-install.sh -R /opt/ -D yes -G $GITREPO  -O $GITORG

COPY run-wrapper.sh /usr/local/bin/run-wrapper.sh
CMD /usr/local/bin/run-wrapper.sh


