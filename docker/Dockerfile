FROM debian:stretch

ENV DEBIAN_FRONTEND noninteractive

# Add non-free packages, needed for snmp-mibs-downloader
RUN sed -i -e 's/main/main non-free contrib/g' /etc/apt/sources.list

# Install dependencies
RUN apt-get update -y -qq && apt-get install -y -qq \
        ipmitool \
        supervisor \
        tcpdump \
        git \
        python3-pip \
        python3 \
        python3-dev \
        wget &&\
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy the app from the host folder (probably a cloned repo) to the container
RUN useradd -m conpot
WORKDIR /opt/
RUN git clone https://github.com/mushorg/conpot.git
RUN chown conpot:conpot -R /opt/conpot

# Install Python requirements
USER conpot
ENV PATH=$PATH:/home/conpot/.local/bin
WORKDIR /opt/conpot
RUN pip3 install --user --no-cache-dir coverage
RUN pip3 install --user --no-cache-dir -r requirements.txt

# Run test cases
RUN py.test -v

# Install the Conpot application
RUN python3.5 setup.py install --user --prefix=
USER root
WORKDIR /
RUN rm -rf /opt/conpot /tmp/* /var/tmp/*
RUN mkdir -p /etc/conpot /var/log/conpot /usr/share/wireshark && \
    wget https://github.com/wireshark/wireshark/raw/master/manuf -o /usr/share/wireshark/manuf

# Create directories
RUN mkdir -p /var/log/conpot/
RUN mkdir -p /data/tftp/
RUN chown conpot:conpot /var/log/conpot
RUN chown conpot:conpot -R /data

# Clean
RUN apt-get remove --purge -y git wget build-essential python3-dev python3-pip && \
    apt-get autoremove -y --purge && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#EXPOSE 80 102 161/udp 502 21 69/udp
USER conpot
WORKDIR /home/conpot
ENV USER=conpot

CMD ["/home/conpot/.local/bin/conpot", "--template", "default", "--logfile", "/var/log/conpot/conpot.log", "-f", "--temp_dir", "/tmp" ]
