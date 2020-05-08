FROM centos:7.7.1908

MAINTAINER Justas Balcas <jbalcas@caltech.edu>
ENV GITREPO siterm
ENV GITORG sdn-sense
ENV GITBR master

RUN adduser apache -U -u 48

RUN mkdir -p /opt/ && mkdir -p /opt/config/fe/ && mkdir -p /opt/dtnrmcode
RUN mkdir -p /etc/httpd/certs/ && mkdir -p /etc/httpd/conf.d/ && mkdir -p /etc/grid-security/certificates
RUN yum -y install git sudo && yum clean all
RUN cd /opt/dtnrmcode && git clone -b $GITBR https://github.com/$GITORG/$GITREPO
RUN cd /opt/dtnrmcode/$GITREPO/installers/ && sudo sh ./fresh-siterm-fe-install.sh -R /opt/ -D yes -G $GITREPO -O $GITORG -B $GITBR

RUN mkdir -p /opt/config/fe/{LookUpService,PolicyService,ProvisioningService}
RUN find /opt/config/fe/ -type f -exec chmod 0644 {} \;
RUN find /opt/config/fe/ -type d -exec chmod 0755 {} \;
RUN chown apache:apache -R /opt/config/fe/
COPY sqlite.db /opt/config/fe/
RUN rm -f /etc/httpd/conf.d/ssl.conf

EXPOSE 80 443
COPY run-wrapper.sh /usr/local/bin/run-wrapper.sh
CMD /usr/local/bin/run-wrapper.sh

