FROM python:2

ENV DEBIAN_FRONTEND noninteractive

# Add non-free packages, needed for snmp-mibs-downloader
RUN sed -i -e 's/main/main non-free contrib/g' /etc/apt/sources.list

# Install dependencies
RUN apt-get update -y -qq && apt-get install -y -qq \
        libmysqlclient-dev \
        libxslt1-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy the app from the host folder (probably a cloned repo) to the container
COPY ./ /opt/conpot/
WORKDIR /opt/conpot

# Install Python requirements
RUN pip install --no-cache-dir coverage
RUN pip install --no-cache-dir -r requirements.txt

# Run test cases
RUN coverage run --timid --source=conpot setup.py test

# Install the Conpot application
RUN python setup.py install
RUN rm -rf /opt/conpot /tmp/* /var/tmp/*

# Create directories
RUN mkdir -p /var/log/conpot/

VOLUME /var/log/conpot/

EXPOSE 80 102 161/udp 502

CMD ["/usr/local/bin/conpot", "--template", "default", "--logfile", "/var/log/conpot/conpot.log"]
