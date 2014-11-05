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
    git clone https://github.com/glastopf/modbus-tk.git
    cd modbus-tk
    python setup.py install
    cd ..
    git clone https://github.com/glastopf/conpot.git
    cd conpot
    python setup.py install

Basic configuration
-------------------

Basic configuration options are provided in the default configuration file:
::

    [modbus]
    host = 0.0.0.0
    port = 502

    [snmp]
    host = 0.0.0.0
    port = 161

    [http]
    host = 0.0.0.0
    port = 80

    [sqlite]
    enabled = False

    [hpfriends]
    enabled = False
    host = hpfriends.honeycloud.net
    port = 20000
    ident = 3Ykf9Znv
    secret = 4nFRhpm44QkG9cvD
    channels = ["conpot.events", ]

    [fetch_public_ip]
    enabled = True
    url = http://api-sth01.exip.org/?call=ip

Please note that by enabling hpfriends your conpot installation will automatically transmit attack data to The Honeynet
Project. The fetch_public_ip option enables fetching the honeypot public ip address from a external resource.

Example usage
--------------

::

    box$ conpot
    2013-04-12 16:09:25,620 Added slave with id 1.
    2013-04-12 16:09:25,621 Added block a to slave 1. (type=1, start=1, size=128)
    2013-04-12 16:09:25,622 Setting value at addr 1 to [random.randint(0,1) for b in range(0,128)].
    2013-04-12 16:09:25,623 Added block d to slave 2. (type=3, start=40001, size=8)
    2013-04-12 16:09:25,623 Conpot initialized using the S7-200 template.
    2013-04-12 16:09:25,623 Serving on: ('0.0.0.0', 502)
    2013-04-12 16:09:27,141 New connection from 127.0.0.1:61493. (b763654f-c9d8-45ae-b35a-824dfc220911)
    2013-04-12 16:09:27,141 Modbus traffic from 127.0.0.1: {'request_pdu': '0100010008', 'function_code': 1, 'slave_id': 1, 'response_pdu': '010132'} (b763654f-c9d8-45ae-b35a-824dfc220911)
    2013-04-12 16:09:27,142 Modbus traffic from 127.0.0.1: {'request_pdu': '0f0001000801ff', 'function_code': 15, 'slave_id': 1, 'response_pdu': '0f00010008'} (b763654f-c9d8-45ae-b35a-824dfc220911)
    2013-04-12 16:09:27,143 Modbus traffic from 127.0.0.1: {'request_pdu': '0100010008', 'function_code': 1, 'slave_id': 1, 'response_pdu': '0101ff'} (b763654f-c9d8-45ae-b35a-824dfc220911)
    2013-04-12 16:09:27,144 Client disconnected. (b763654f-c9d8-45ae-b35a-824dfc220911)

