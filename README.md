# Conpot

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and methods of adversaries targeting industrial control systems

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

## Example output
``` shell
box$ python conpot_ics_server.py 
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
```
