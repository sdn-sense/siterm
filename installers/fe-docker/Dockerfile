FROM centos:7

MAINTAINER Justas Balcas <jbalcas@caltech.edu>
ENV GITREPO siterm
ENV GITORG sdn-sense

RUN adduser apache -U -u 48

RUN mkdir -p /opt/ && mkdir -p /opt/config/fe/ && mkdir -p /opt/dtnrmcode
RUN mkdir -p /etc/httpd/certs/ && mkdir -p /etc/httpd/conf.d/
RUN yum -y install git && yum clean all
RUN cd /opt/dtnrmcode && git clone https://github.com/$GITORG/$GITREPO
RUN cd /opt/dtnrmcode/$GITREPO/installers/ && sudo sh ./fresh-siterm-fe-install.sh -R /opt/ -D yes -G $GITREPO  -O $GITORG

RUN mkdir -p /opt/config/fe/{LookUpService,PolicyService,ProvisioningService}
RUN find /opt/config/fe/ -type f -exec chmod 0644 {} \;
RUN find /opt/config/fe/ -type d -exec chmod 0755 {} \;
RUN chown apache:apache -R /opt/config/fe/
COPY sqlite.db /opt/config/fe/

EXPOSE 80 443
COPY run-wrapper.sh /usr/local/bin/run-wrapper.sh
CMD /usr/local/bin/run-wrapper.sh

