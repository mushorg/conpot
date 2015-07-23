FROM ubuntu:14.04.1

ENV DEBIAN_FRONTEND noninteractive

# Prepare source.list
RUN sed -i '1ideb mirror://mirrors.ubuntu.com/mirrors.txt trusty main universe multiverse' /etc/apt/sources.list && \
    sed -i '1ideb mirror://mirrors.ubuntu.com/mirrors.txt trusty-updates main universe multiverse' /etc/apt/sources.list && \
    sed -i '1ideb mirror://mirrors.ubuntu.com/mirrors.txt trusty-backports main universe multiverse' /etc/apt/sources.list && \
    sed -i '1ideb mirror://mirrors.ubuntu.com/mirrors.txt trusty-security main universe multiverse' /etc/apt/sources.list

# Install dependencies
RUN apt-get update && apt-get install -y \
        git \
        libmysqlclient-dev \
        libsmi2ldbl \
        libxslt1-dev \
        python \
        python-dev \
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
