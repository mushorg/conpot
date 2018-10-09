FROM python:3.5

ENV DEBIAN_FRONTEND noninteractive

# Add non-free packages, needed for snmp-mibs-downloader
RUN sed -i -e 's/main/main non-free contrib/g' /etc/apt/sources.list

# Install dependencies
RUN apt-get update -y -qq && apt-get install -y -qq \
        default-libmysqlclient-dev \
        ipmitool \
        supervisor \
        tcpdump \
        libxslt1-dev && \
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
RUN pip install --user --no-cache-dir coverage
RUN pip install --user --no-cache-dir -r requirements.txt

# Run test cases
RUN py.test -v

# Install the Conpot application
RUN python3.5 setup.py install --user --prefix=
USER root
WORKDIR /
COPY conpot.conf /etc/supervisor/conf.d/
RUN rm -rf /opt/conpot /tmp/* /var/tmp/*

# Create directories
RUN mkdir -p /var/log/conpot/
RUN chown conpot:conpot /var/log/conpot

#EXPOSE 80 102 161/udp 502 21 69/udp

CMD ["/usr/bin/supervisord", "-nc", "/etc/supervisor/supervisord.conf"]
