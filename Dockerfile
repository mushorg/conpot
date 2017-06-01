FROM python:2

ENV DEBIAN_FRONTEND noninteractive

# Add non-free packagesto, needed for snmp-mibs-downloader
RUN sed -i -e 's/main/main non-free contrib/g' /etc/apt/sources.list

# Install dependencies
RUN apt-get update -y -qq && apt-get install -y -qq \
        libmysqlclient-dev \
        libsmi2ldbl \
        libxslt1-dev \
        snmp-mibs-downloader && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Clone git repo and build the honeypot
RUN cd /opt/ && \
    git clone https://github.com/mushorg/conpot.git && \
    cd conpot/ && \
    python setup.py install && \
    rm -rf /opt/conpot /tmp/* /var/tmp/*

## Create directories
RUN mkdir -p /opt/myhoneypot/var

WORKDIR /opt/myhoneypot
VOLUME /opt/myhoneypot

EXPOSE 80 102 161/udp 502

CMD ["/usr/local/bin/conpot", "--template", "default", "--logfile", "/opt/myhoneypot/var/conpot.log"]
