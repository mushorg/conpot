FROM alpine:3.8 as conpot-builder


# Install dependencies
RUN apk add --no-cache ipmitool tcpdump git python3-dev build-base wget py-cffi libxslt-dev openssl-dev libffi-dev

# Copy the app from the host folder (probably a cloned repo) to the container
RUN adduser -s /bin/ash -D conpot
WORKDIR /opt/
RUN git clone --depth=1 https://github.com/mushorg/conpot.git
RUN chown conpot:conpot -R /opt/conpot

# Install Python requirements
USER conpot
WORKDIR /opt/conpot
RUN pip3 install --user --no-cache-dir -U pip setuptools
RUN pip3 install --user --no-cache-dir coverage
RUN pip3 install --user --no-cache-dir -r requirements.txt

# Install the Conpot application
RUN python3 setup.py install --user --prefix=

# Run test cases
ENV PATH=$PATH:/home/conpot/.local/bin
RUN py.test -v

RUN pip3 uninstall -y setuptools

WORKDIR /home/conpot

FROM alpine:3.8

USER root


RUN apk add --no-cache ipmitool ca-certificates tcpdump python3 wget py-cffi libxslt openssl

RUN adduser -s /bin/ash -D conpot
WORKDIR /home/conpot
COPY --from=conpot-builder --chown=conpot:conpot /home/conpot/.local/ /home/conpot/.local/
RUN mkdir -p /etc/conpot /var/log/conpot /usr/share/wireshark && \
    wget https://github.com/wireshark/wireshark/raw/master/manuf -o /usr/share/wireshark/manuf

# Create directories
RUN mkdir -p /var/log/conpot/
RUN mkdir -p /data/tftp/
RUN chown conpot:conpot /var/log/conpot
RUN chown conpot:conpot -R /data

# Clean
RUN apk del --purge wget ca-certificates

USER conpot
WORKDIR /home/conpot
ENV USER=conpot

CMD ["/home/conpot/.local/bin/conpot", "--template", "default", "--logfile", "/var/log/conpot/conpot.log", "-f", "--temp_dir", "/tmp" ]
