Ubuntu 12.04 LTS  / 14.04 LTS
======================================

Installation
------------

You need to add multiverse to the source, like;
::

$ sudo vim /etc/apt/sources.list

Add the following line:

deb http://dk.archive.ubuntu.com/ubuntu precise main multiverse

Install dependencies:
::

    sudo apt-get install libmysqlclient-dev libsmi2ldbl snmp-mibs-downloader python-dev libevent-dev \
    libxslt1-dev libxml2-dev python-pip python-mysqldb pkg-config libvirt-dev


The stable version of ConPot can be downloaded from PyPI:
::

    pip install conpot


The development version can be cloned from github:
::

    cd /opt
    git clone git@github.com:mushorg/conpot.git
    cd conpot
    python setup.py install


