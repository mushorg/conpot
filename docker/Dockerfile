FROM alpine:3.12.1 as conpot-builder

# Install dependencies
RUN apk update \
    && apk add --no-cache ipmitool git python3-dev build-base py-cffi libxslt-dev libffi-dev py3-pip \
    && apk add --virtual build-deps gcc musl-dev \
    && apk add --no-cache mariadb-dev

# Copy the app from the host folder (probably a cloned repo) to the container
RUN adduser -s /bin/ash -D conpot

WORKDIR /opt/
RUN git clone --depth=1 https://github.com/mushorg/conpot.git
RUN chown conpot:conpot -R /opt/conpot

# Install Python requirements
USER conpot

WORKDIR /opt/conpot

ENV PATH=$PATH:/home/conpot/.local/bin

RUN pip3 install --user --no-cache-dir -U pip wheel
RUN pip3 install --user --no-cache-dir setuptools
RUN pip3 install --user --no-cache-dir -r requirements.txt

# Install the Conpot application
RUN python3 setup.py install --user --prefix=


# Run container
FROM alpine:3.12.1

RUN apk update \
    && apk add --no-cache ipmitool ca-certificates python3 wget py-cffi libxslt openssl

RUN adduser -s /bin/ash -D conpot
WORKDIR /home/conpot

COPY --from=conpot-builder --chown=conpot:conpot /home/conpot/.local/ /home/conpot/.local/
RUN mkdir -p /etc/conpot /var/log/conpot /usr/share/wireshark \
    && wget https://github.com/wireshark/wireshark/raw/master/manuf -o /usr/share/wireshark/manuf

# Create directories
RUN mkdir -p /var/log/conpot/ \
    && mkdir -p /data/tftp/ \
    && chown conpot:conpot /var/log/conpot \
    && chown conpot:conpot -R /data

# Clean
RUN apk del --purge wget ca-certificates

USER conpot
WORKDIR /home/conpot
ENV USER=conpot
ENTRYPOINT ["/home/conpot/.local/bin/conpot"]
CMD ["--template", "default", "--logfile", "/var/log/conpot/conpot.log", "-f", "--temp_dir", "/tmp" ]
