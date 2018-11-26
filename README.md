# Conpot

[![Build Status](https://travis-ci.org/mushorg/conpot.svg?branch=master)](https://travis-ci.org/mushorg/conpot)
[![Code Health](https://landscape.io/github/mushorg/conpot/master/landscape.png)](https://landscape.io/github/mushorg/conpot/master)
[![Python Version](https://img.shields.io/pypi/pyversions/conpot.svg)](https://pypi.python.org/pypi/Conpot) 
[![PyPI version](https://badge.fury.io/py/Conpot.svg)](https://badge.fury.io/py/Conpot)
[![Docs](https://readthedocs.org/projects/conpot/badge/?version=latest)](https://conpot.readthedocs.io/en/latest/)
[![Coverage Status](https://coveralls.io/repos/github/mushorg/conpot/badge.svg?branch=master)](https://coveralls.io/github/mushorg/conpot?branch=master)

## About

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and
methods of adversaries targeting industrial control systems

## Documentation

The build of the documentations [source](https://github.com/mushorg/conpot/tree/master/docs/source) can be found [here](https://conpot.readthedocs.io/en/latest/). There you will also find the instructions on how to [install](https://conpot.readthedocs.io/en/latest/installation/ubuntu.html) conpot and the [FAQ](https://conpot.readthedocs.io/en/latest/faq.html).

## Easy install using Docker

[![Docker Build Status](https://img.shields.io/docker/build/honeynet/conpot.svg)](https://hub.docker.com/r/honeynet/conpot)
[![Docket Image Size](https://img.shields.io/microbadger/image-size/honeynet/conpot.svg)](https://hub.docker.com/r/honeynet/conpot)
[![Docker Pulls](https://img.shields.io/docker/pulls/honeynet/conpot.svg)](https://hub.docker.com/r/honeynet/conpot)

#### Via a pre-built image

1. Install [Docker](https://docs.docker.com/engine/installation/)
2. Run `docker pull honeynet/conpot`
3. Run `docker run -it -p 80:80 -p 102:102 -p 502:502 -p 161:161/udp --network=bridge honeynet/conpot:latest /bin/sh`
4. Finally run `conpot -f --template default`

Navigate to ``http://MY_IP_ADDRESS`` to confirm the setup.

#### Build docker image from source

1. Install [Docker](https://docs.docker.com/engine/installation/)
2. Clone this repo with `git clone https://github.com/mushorg/conpot.git` and `cd conpot/docker`
3. Run `docker build -t conpot .`
4. Run `docker run -it -p 80:8800 -p 102:10201 -p 502:5020 -p 161:16100/udp -p 47808:47808/udp -p 623:6230/udp -p 21:2121 -p 69:6969/udp -p 44818:44818 --network=bridge conpot`

Navigate to `http://MY_IP_ADDRESS` to confirm the setup. 

#### Build from source and run with docker-compose

1. Install [docker-compose](https://docs.docker.com/compose/install/) 
2. Clone this repo with `git clone https://github.com/mushorg/conpot.git` and `cd conpot/docker`
3. Build the image with `docker-compose build`
4. Test if everything is running correctly with `docker-compose up`
5. Permanently run as a daemon with `docker-compose up -d`

## Sample output
::
          
    # conpot --template default  
                         _                                                                                                    
     ___ ___ ___ ___ ___| |_                                                                                                
    |  _| . |   | . | . |  _|                                                                                               
    |___|___|_|_|  _|___|_|                                                                                                 
                |_|                                                                                                         
                                                                                                                          
    Version 0.6.0                                                                                                           
    MushMush Foundation                                                                                                     

    2018-08-09 19:13:15,085 Initializing Virtual File System at ConpotTempFS/__conpot__ootc_k3j. Source specified : tar://conpot-0.6.0-py3.6/conpot/data.tar
    2018-08-09 19:13:15,100 Please wait while the system copies all specified files
    2018-08-09 19:13:15,172 Fetched x.x.x.x as external ip.
    2018-08-09 19:13:15,175 Found and enabled ('modbus', <conpot.protocols.modbus.modbus_server.ModbusServer object at 0x7f1af52231d0>) protocol.
    2018-08-09 19:13:15,177 Found and enabled ('s7comm', <conpot.protocols.s7comm.s7_server.S7Server object at 0x7f1af5ad1f60>) protocol.
    2018-08-09 19:13:15,178 Found and enabled ('http', <conpot.protocols.http.web_server.HTTPServer object at 0x7f1af4fc2630>) protocol.
    2018-08-09 19:13:15,179 Found and enabled ('snmp', <conpot.protocols.snmp.snmp_server.SNMPServer object at 0x7f1af4fc2710>) protocol.
    2018-08-09 19:13:15,181 Found and enabled ('bacnet', <conpot.protocols.bacnet.bacnet_server.BacnetServer object at 0x7f1af4fc22e8>) protocol.
    2018-08-09 19:13:15,182 Found and enabled ('ipmi', <conpot.protocols.ipmi.ipmi_server.IpmiServer object at 0x7f1af5aaa1d0>) protocol.
    2018-08-09 19:13:15,185 Found and enabled ('enip', <conpot.protocols.enip.enip_server.EnipServer object at 0x7f1af5aaa0f0>) protocol.
    2018-08-09 19:13:15,199 Found and enabled ('ftp', <conpot.protocols.ftp.ftp_server.FTPServer object at 0x7f1af4fcec18>) protocol.
    2018-08-09 19:13:15,206 Found and enabled ('tftp', <conpot.protocols.tftp.tftp_server.TftpServer object at 0x7f1af4fcef28$) protocol.
    2018-08-09 19:13:15,206 No proxy template found. Service will remain unconfigured/stopped.                                
    2018-08-09 19:13:15,206 Modbus server started on: ('0.0.0.0', 5020)                                                       
    2018-08-09 19:13:15,206 S7Comm server started on: ('0.0.0.0', 10201)                                                      
    2018-08-09 19:13:15,207 HTTP server started on: ('0.0.0.0', 8800)                                                         
    2018-08-09 19:13:15,402 SNMP server started on: ('0.0.0.0', 16100)                                                        
    2018-08-09 19:13:15,403 Bacnet server started on: ('0.0.0.0', 47808)                                                      
    2018-08-09 19:13:15,403 IPMI server started on: ('0.0.0.0', 6230)                                                         
    2018-08-09 19:13:15,403 handle server PID [23183] running on ('0.0.0.0', 44818)                                           
    2018-08-09 19:13:15,404 handle server PID [23183] responding to external done/disable signal in object 139753672309064
    2018-08-09 19:13:15,404 FTP server started on: ('0.0.0.0', 2121)                                                          
    2018-08-09 19:13:15,404 Starting TFTP server at ('0.0.0.0', 6969)
