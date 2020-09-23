FROM centos:7.7.1908

MAINTAINER Justas Balcas <jbalcas@caltech.edu>
RUN yum -y install wget
RUN wget https://github.com/prometheus/node_exporter/releases/download/v1.0.1/node_exporter-1.0.1.linux-amd64.tar.gz
RUN tar -xvzf node_exporter-1.0.1.linux-amd64.tar.gz
RUN useradd -rs /bin/false nodeusr
RUN mv node_exporter-1.0.1.linux-amd64/node_exporter /usr/local/bin/

EXPOSE 9100

ENTRYPOINT [ "/usr/local/bin/node_exporter" ]

