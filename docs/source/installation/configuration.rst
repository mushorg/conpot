Basic Configuration
===================

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

