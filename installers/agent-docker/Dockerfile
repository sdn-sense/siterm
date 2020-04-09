FROM centos:7

MAINTAINER Justas Balcas <jbalcas@caltech.edu>

RUN mkdir -p /opt/ && mkdir -p /opt/config/
RUN  yum -y install git
RUN git clone https://github.com/sdn-sense/siterm-installers
RUN cd siterm-installers && sudo sh ./fresh-siterm-agent-install.sh -R /opt/ -D yes

COPY run-wrapper.sh /usr/local/bin/run-wrapper.sh
CMD /usr/local/bin/run-wrapper.sh


