Conpot |Build Status|
=======================

.. |Build Status| image:: https://travis-ci.org/glastopf/conpot.png?branch=master
                       :target: https://travis-ci.org/glastopf/conpot

ABOUT
-----

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and
methods of adversaries targeting industrial control systems

HPFEEDS
-------

The honeypot has hpfeeds, our central logging feature disabled by
default. By sending your data via hpfeeds you agree that your data
might be shared with 3rd parties. If you are interested in the data
collected by Conpot instances, please contact Lukas at
glaslos@gmail.com

SUPPORT
-------

Thanks to JetBrains for free PyCharm licenses!

INSTALL
-------
Install instruction can be found `here <https://github.com/glastopf/conpot/blob/master/docs/source/installation/ubuntu.rst>`_.

SAMPLE OUTPUT
-------------

.. code-block:: shell

    # conpot 
    
                           _
       ___ ___ ___ ___ ___| |_
      |  _| . |   | . | . |  _|
      |___|___|_|_|  _|___|_|
                  |_|
    
      Version 0.1.0
      Glastopf Project
    
    2013-05-11 18:47:16,434 Starting Conpot using template found in: /Users/jkv/repos/conpot/conpot/templates/default.xml
    2013-05-11 18:47:16,435 Starting Conpot using configuration found in: /Users/jkv/repos/conpot/conpot/conpot.cfg
    <configuration of slaves>
    2013-05-11 18:47:16,435 Added slave with id 1.
    2013-05-11 18:47:16,435 Added block a to slave 1. (type=1, start=1, size=128)
    2013-05-11 18:47:16,436 Setting value at addr 1 to [random.randint(0,1) for b in range(0,128)].
    2013-05-11 18:47:16,437 Conpot initialized using the S7-200 template.
    2013-05-11 18:47:16,437 Modbus server started on: ('X.Y.Z.P', 502)
    2013-05-11 18:47:16,569 Registered: MibScalar((1, 3, 6, 1, 2, 1, 1, 1), DisplayString())
    <snip>
    2013-05-11 18:47:16,570 Starting SNMP server.
    <attackers reads from modbus>
    2013-05-11 18:49:42,315 Modbus traffic from X.Y.Z.P: {'function_code': 1, 'slave_id': 1, 'request': '0100010080', 'response': '011056412da0b5b5972c8e6f9204b561870b'} (1bfd5020-b0a1-41d1-b1ec-00a68321edca)
    2013-05-11 18:49:42,326 Client disconnected. (1bfd5020-b0a1-41d1-b1ec-00a68321edca)
    2013-05-11 18:49:42,326 New connection from X.Y.Z.P:49790. (3488c9d3-6e6d-4280-b3e1-32d70aa9f3aa)
    <attackers write to modbus - if seen in the wild this would VERY malicious!>
    2013-05-11 18:49:42,326 Modbus traffic from X.Y.Z.P: {'function_code': 15, 'slave_id': 1, 'request': '0f0001000801c9', 'response': '0f00010008'} (3488c9d3-6e6d-4280-b3e1-32d70aa9f3aa)
    <attacker probes with snmp (snmpwalk -Os -c public -v 1 X.Y.Z.P system)>
    2013-05-11 18:49:51,112 SNMPv1 request from ('X.Y.Z.P', 60934), Type: GetNextRequestPDU, Community: public, Oid: 1.3.6.1.2.1.1, Value: 
    2013-05-11 18:49:51,118 SNMPv1 reply to ('X.Y.Z.P', 60934), Type: GetResponsePDU, Community: public, Oid: 1.3.6.1.2.1.1.1.0, Value: Siemens, SIMATIC, S7-200
    2013-05-11 18:49:51,119 SNMPv1 request from ('X.Y.Z.P', 60934), Type: GetNextRequestPDU, Community: public, Oid: 1.3.6.1.2.1.1.1.0, Value: 
    2013-05-11 18:49:51,121 SNMPv1 reply to ('X.Y.Z.P', 60934), Type: GetResponsePDU, Community: public, Oid: 1.3.6.1.2.1.1.2.0, Value: 0.0

