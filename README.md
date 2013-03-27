# Conpot

Conpot is a ICS honeypot.

## Origin

Code is based on http://scadahoneynet.sourceforge.net/ and examples from https://code.google.com/p/modbus-tk/

## Installation

You need Python2.7 and pip:

    [sudo] apt-get install python2.7 python-pip git

For the requiremenst covered by PyPi, run:

    [sudo] pip install -r requirements.txt

For hpfeeds:

    cd /opt
    git clone git://github.com/rep/hpfeeds.git
    cd hpfeeds/
    python setup.py install

And modbus_tk

    cd /opt
    wget https://code.google.com/p/modbus-tk/downloads/detail?name=modbus-tk-0.4.2.zip
    unzip modbus-tk-0.4.2.zip
    cd modbus-tk-0.4.2
    python setup.py install
