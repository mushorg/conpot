Debian
======================================

Tested Versions
---------------

* 7.2.0 64bit
* 6.0.7 64bit


This was tested on a minimal installation w/o desktop packages.

Installation
------------

Install dependencies:
::

    apt-get install git libsmi2ldbl smistrip libxslt1-dev python-dev libevent-dev
    
Debian 6 specific
::

    apt-get install python-pip
    pip install argparse


The package snmp-mibs-downloader is non-free so we have to install the package manually. All dependencies are covered by installing smistrip. Get the package from here:
::

    wget $package_url
    dpkg -i $package_name

Alternatively, add "non-free" to the /etc/apt/sources.list
::

    deb http://ftp.nl.debian.org/debian squeeze main non-free 

And do an 
::

    apt-get update

followed by 
::

    apt-get install snmp-mibs-downloader


The stable version of Conpot can be downloaded from PyPI:
::

    pip install conpot


The development version can be cloned from github - but we need a modified modbus-tk first.
::

    cd /opt
    git clone https://github.com/mushorg/modbus-tk.git
    cd modbus-tk
    python setup.py install
    cd ..
    git clone https://github.com/mushorg/conpot.git
    cd conpot
    python setup.py install


