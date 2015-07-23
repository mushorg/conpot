Conpot |travis badge| |landscape badge| |downloads badge| |version badge|
=======================

.. |travis badge| image:: https://img.shields.io/travis/mushorg/conpot/master.svg
   :target: https://travis-ci.org/mushorg/conpot
.. |landscape badge| image:: https://landscape.io/github/mushorg/conpot/master/landscape.png
   :target: https://landscape.io/github/mushorg/conpot/master
   :alt: Code Health
.. |downloads badge| image:: https://img.shields.io/pypi/dm/conpot.svg
   :target: https://pypi.python.org/pypi/Conpot/
.. |version badge| image:: https://img.shields.io/pypi/v/conpot.svg
   :target: https://pypi.python.org/pypi/Conpot/
.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/mushorg/conpot
   :target: https://gitter.im/mushorg/conpot?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge

ABOUT
-----

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and
methods of adversaries targeting industrial control systems

DOCUMENTATION
-------------

The build of the documentations `source <https://github.com/mushorg/conpot/tree/master/docs/source>`_ can be 
found `here <http://mushorg.github.io/conpot/>`_. There you will also find the instructions on how to 
`install <http://mushorg.github.io/conpot/installation/ubuntu.html>`_ conpot and the 
`FAQ <http://mushorg.github.io/conpot/faq.html>`_.

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

SAMPLE OUTPUT
-------------

.. code-block:: shell

    # conpot --template default
    
                           _
       ___ ___ ___ ___ ___| |_
      |  _| . |   | . | . |  _|
      |___|___|_|_|  _|___|_|
                  |_|
    
      Version 0.4.0
      MushMush Foundation

    2015-05-27 16:05:08,355 Starting Conpot using template: /usr/local/lib/python2.7/dist-packages/Conpot-0.4.0-py2.7.egg/conp
    2015-05-27 16:05:08,366 Starting Conpot using configuration found in: /usr/local/lib/python2.7/dist-packages/Conpot-0.4.0-
    2015-05-27 16:05:08,428 Starting new HTTP connection (1): www.telize.com
    2015-05-27 16:05:08,861 Fetched xxx.xxx.xxx.xxx as external ip.
    2015-05-27 16:05:08,891 Conpot modbus initialized
    2015-05-27 16:05:08,893 Found and enabled ('modbus', <class conpot.protocols.modbus.modbus_server.ModbusServer at 0xb4f1e3
    2015-05-27 16:05:08,898 Conpot S7Comm initialized
    2015-05-27 16:05:08,899 Found and enabled ('s7comm', <class 'conpot.protocols.s7comm.s7_server.S7Server'>) protocol.
    2015-05-27 16:05:08,902 Found and enabled ('http', <class 'conpot.protocols.http.web_server.HTTPServer'>) protocol.
    2015-05-27 16:05:08,905 Found and enabled ('snmp', <class 'conpot.protocols.snmp.snmp_server.SNMPServer'>) protocol.
    2015-05-27 16:05:08,915 Conpot Bacnet initialized using the /usr/local/lib/python2.7/dist-packages/Conpot-0.4.0-py2.7.egg/
    2015-05-27 16:05:08,916 Found and enabled ('bacnet', <class 'conpot.protocols.bacnet.bacnet_server.BacnetServer'>) protoco
    2015-05-27 16:05:08,922 IPMI BMC initialized.
    2015-05-27 16:05:08,923 Conpot IPMI initialized using /usr/local/lib/python2.7/dist-packages/Conpot-0.4.0-py2.7.egg/conpot
    2015-05-27 16:05:08,923 Found and enabled ('ipmi', <class 'conpot.protocols.ipmi.ipmi_server.IpmiServer'>) protocol.
    2015-05-27 16:05:09,003 No proxy template found. Service will remain unconfigured/stopped.
    2015-05-27 16:05:09,015 Modbus server started on: ('0.0.0.0', 502)
    2015-05-27 16:05:09,017 S7Comm server started on: ('0.0.0.0', 102)
    2015-05-27 16:05:09,018 HTTP server started on: ('0.0.0.0', 80)
    2015-05-27 16:05:09,285 SNMP server started on: ('0.0.0.0', 161)
    2015-05-27 16:05:09,286 Bacnet server started on: ('0.0.0.0', 47808)
    2015-05-27 16:05:09,286 IPMI server started on: ('0.0.0.0', 623)
    2015-05-27 16:05:09,287 connecting to hpfriends.honeycloud.net:20000
    2015-05-27 16:05:14,006 Privileges dropped, running as nobody/nogroup.

