# Conpot

[![Travis CI](https://img.shields.io/travis/mushorg/conpot/master.svg)](https://travis-ci.org/mushorg/conpot)
[![Code Health](https://landscape.io/github/mushorg/conpot/master/landscape.png)](https://landscape.io/github/mushorg/conpot/master)
[![Downloads Counter](https://img.shields.io/pypi/dm/conpot.svg)](https://pypi.python.org/pypi/Conpot/) 
[![Version](https://img.shields.io/pypi/v/conpot.svg)](https://pypi.python.org/pypi/Conpot/)


## About

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and
methods of adversaries targeting industrial control systems

## Documentation

The build of the documentations [source](https://github.com/mushorg/conpot/tree/master/docs/source) can be found [here](http://mushorg.github.io/conpot/). There you will also find the instructions on how to [install](http://mushorg.github.io/conpot/installation/ubuntu.html) conpot and the [FAQ](http://mushorg.github.io/conpot/faq.html).

## Easy install using Docker

#### Via a pre-built image

1. Install [Docker](https://docs.docker.com/engine/installation/)
2. Run `docker pull honeynet/conpot`
3. Run `docker run -it -p 80:80 -p 102:102 -p 502:502 -p 161:161/udp --network=bridge honeynet/conpot:latest /bin/sh`
4. Finally run `conpot --template default`

Navigate to ``http://MY_IP_ADDRESS`` to confirm the setup.

#### Build docker image from source

1. Install [Docker](https://docs.docker.com/engine/installation/)
2. Clone this repo with `git clone https://github.com/mushorg/conpot.git` and `cd conpot`
3. Run `docker build -t conpot .`
4. Run `docker run -it -p 80:80 -p 102:102 -p 502:502 -p 161:161/udp --network=bridge conpot`

Navigate to `http://MY_IP_ADDRESS` to confirm the setup. 

#### Build from source and run with docker-compose

1. Install [docker-compose](https://docs.docker.com/compose/install/) 
2. Clone this repo with `git clone https://github.com/mushorg/conpot.git` and `cd conpot`
3. Build the image with `docker-compose build`
4. Test if everything is running correctly with `docker-compose up`
5. Permanently run as a daemon with `docker-compose up -d`

## HPFEEDS

The honeypot has hpfeeds, our central logging feature disabled by
default. By sending your data via hpfeeds you agree that your data
might be shared with 3rd parties. If you are interested in the data
collected by Conpot instances, please contact Lukas at
glaslos@gmail.com

## Support

Thanks to JetBrains for free PyCharm licenses!

## Sample output


```shell

    # conpot --template default

                           _
       ___ ___ ___ ___ ___| |_
      |  _| . |   | . | . |  _|
      |___|___|_|_|  _|___|_|
                  |_|

      Version 0.5.1
      MushMush Foundation

    2015-11-08 11:24:02,150 Starting Conpot using template: /usr/local/lib/python2.7/dist-packages/Conpot-0.5.0-py2.7.egg/conpot/templates/default
    2015-11-08 11:24:02,150 Starting Conpot using configuration found in: /usr/local/lib/python2.7/dist-packages/Conpot-0.5.0-py2.7.egg/conpot/conpot.cfg
    2015-11-08 11:24:02,291 Fetched xxx.xxx.xxx.xxx as external ip.
    2015-11-08 11:24:02,295 Found and enabled ('modbus', <class conpot.protocols.modbus.modbus_server.ModbusServer at 0x7fe0d70a27a0>) protocol.
    2015-11-08 11:24:02,299 Conpot S7Comm initialized
    2015-11-08 11:24:02,299 Found and enabled ('s7comm', <class 'conpot.protocols.s7comm.s7_server.S7Server'>) protocol.
    2015-11-08 11:24:02,300 Found and enabled ('http', <class 'conpot.protocols.http.web_server.HTTPServer'>) protocol.
    2015-11-08 11:24:02,301 Found and enabled ('snmp', <class 'conpot.protocols.snmp.snmp_server.SNMPServer'>) protocol.
    2015-11-08 11:24:02,302 Conpot Bacnet initialized using the /usr/local/lib/python2.7/dist-packages/Conpot-0.5.0-py2.7.egg/conpot/templates/default/bacnet/bacnet.xml template.
    2015-11-08 11:24:02,303 Found and enabled ('bacnet', <class 'conpot.protocols.bacnet.bacnet_server.BacnetServer'>) protocol.
    2015-11-08 11:24:02,304 IPMI BMC initialized.
    2015-11-08 11:24:02,305 Conpot IPMI initialized using /usr/local/lib/python2.7/dist-packages/Conpot-0.5.0-py2.7.egg/conpot/templates/default/ipmi/ipmi.xml template
    2015-11-08 11:24:02,305 Found and enabled ('ipmi', <class 'conpot.protocols.ipmi.ipmi_server.IpmiServer'>) protocol.
    2015-11-08 11:24:02,305 No proxy template found. Service will remain unconfigured/stopped.
    2015-11-08 11:24:02,305 Modbus server started on: ('0.0.0.0', 502)
    2015-11-08 11:24:02,306 S7Comm server started on: ('0.0.0.0', 102)
    2015-11-08 11:24:02,306 HTTP server started on: ('0.0.0.0', 80)
    2015-11-08 11:24:02,461 SNMP server started on: ('0.0.0.0', 161)
    2015-11-08 11:24:02,462 Bacnet server started on: ('0.0.0.0', 47808)
    2015-11-08 11:24:02,462 IPMI server started on: ('0.0.0.0', 623)
    2015-11-08 11:24:07,307 Privileges dropped, running as "nobody:nobody"
```
