# Conpot

Conpot is a ICS honeypot.

## Origin

Code is based on http://scadahoneynet.sourceforge.net/ and examples from https://code.google.com/p/modbus-tk/

## Installation

You need Python2.7 and pip:

    apt-get install python2.7 python-pip git unzip

For the requiremenst covered by PyPi, run:

    pip install -r requirements.txt

For hpfeeds:

    cd /opt
    git clone git://github.com/rep/hpfeeds.git
    cd hpfeeds/
    python setup.py install

And modbus_tk

    cd /opt
    wget https://modbus-tk.googlecode.com/files/modbus-tk-0.4.2.zip
    unzip modbus-tk-0.4.2.zip -d modbus_tk
    cd modbus_tk
    python setup.py install

And finally ConPot:

    cd /opt
    git clone git@github.com:glastopf/conpot.git
    cd /opt/conpot
    cp config.py.dist config.py

Edit the config.py appropriately.