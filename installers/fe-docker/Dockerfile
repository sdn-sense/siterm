FROM centos:7

MAINTAINER Justas Balcas <jbalcas@caltech.edu>

RUN adduser apache -U -u 48

RUN mkdir -p /opt/ && mkdir -p /opt/config/fe/
RUN mkdir -p /etc/httpd/certs/ && mkdir -p /etc/httpd/conf.d/
RUN yum -y install git sudo && yum clean all
RUN git clone https://github.com/sdn-sense/siterm-installers
RUN cd siterm-installers && sudo sh ./fresh-siterm-fe-install.sh -R /opt/

RUN mkdir -p /opt/config/fe/{LookUpService,PolicyService,ProvisioningService}
RUN find /opt/config/fe/ -type f -exec chmod 0644 {} \;
RUN find /opt/config/fe/ -type d -exec chmod 0755 {} \;
RUN chown apache:apache -R /opt/config/fe/
COPY sqlite.db /opt/config/fe/

EXPOSE 80 443
COPY run-wrapper.sh /usr/local/bin/run-wrapper.sh
CMD /usr/local/bin/run-wrapper.sh


