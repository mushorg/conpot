Conpot |travis badge| |landscape badge| |downloads badge| |version badge|
=======================

.. |travis badge| image:: https://travis-ci.org/glastopf/conpot.png?branch=master
   :target: https://travis-ci.org/glastopf/conpot
.. |landscape badge| image:: https://landscape.io/github/glastopf/conpot/master/landscape.png
   :target: https://landscape.io/github/glastopf/conpot/master
   :alt: Code Health
.. |downloads badge| image:: https://pypip.in/v/Conpot/badge.png
   :target: https://pypi.python.org/pypi/Conpot/
.. |version badge| image:: https://pypip.in/d/Conpot/badge.png
   :target: https://pypi.python.org/pypi/Conpot/

ABOUT
-----

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and
methods of adversaries targeting industrial control systems

DOCUMENTATION
-------------

The build of the documentations `source <https://github.com/glastopf/conpot/tree/master/docs/source>`_ can be 
found `here <http://glastopf.github.io/conpot/>`_. There you will also find the instructions on how to 
`install <http://glastopf.github.io/conpot/installation/ubuntu.html>`_ conpot and the 
`FAQ <http://glastopf.github.io/conpot/faq.html>`_.

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

    # conpot 
    
                           _
       ___ ___ ___ ___ ___| |_
      |  _| . |   | . | . |  _|
      |___|___|_|_|  _|___|_|
                  |_|
    
      Version 0.2.2
      Glastopf Project

    2013-06-23 23:39:56,593 Starting Conpot using template found in: /opt/conpot/conpot/templates/default.xml
    2013-06-23 23:39:56,593 Starting Conpot using configuration found in: /opt/conpot/conpot/conpot.cfg
    2013-06-23 23:39:56,593 Starting Conpot using www templates found in: /opt/conpot/conpot/www/
    2013-06-23 23:39:56,594 Added slave with id 1.
    2013-06-23 23:39:56,594 Added block a to slave 1. (type=1, start=1, size=128)
    2013-06-23 23:39:56,595 Setting value at addr 1 to [random.randint(0,1) for b in range(0,128)].
    2013-06-23 23:39:56,595 Added block b to slave 1. (type=2, start=10001, size=32)
    2013-06-23 23:39:56,595 Setting value at addr 10001 to [random.randint(0,1) for b in range(0,32)].
    2013-06-23 23:39:56,595 Added slave with id 2.
    2013-06-23 23:39:56,595 Added block c to slave 2. (type=4, start=30001, size=8)
    2013-06-23 23:39:56,595 Setting value at addr 30001 to [random.randint(0,1) for b in range(0,8)].
    2013-06-23 23:39:56,596 Added block d to slave 2. (type=3, start=40001, size=8)
    2013-06-23 23:39:56,596 Conpot initialized using the S7-200 template.
    2013-06-23 23:39:56,596 Modbus server started on: ('0.0.0.0', 502)
    2013-06-23 23:39:56,683 Registered OID (1, 3, 6, 1, 2, 1, 1, 1) instance (0,) (sysDescr, SNMPv2-MIB) : Siemens, SIMATIC, S7-200
    2013-06-23 23:39:56,683 Registered OID (1, 3, 6, 1, 2, 1, 1, 2) instance (0,) (sysObjectID, SNMPv2-MIB) : 0.0
    2013-06-23 23:39:56,683 Registered OID (1, 3, 6, 1, 2, 1, 1, 4) instance (0,) (sysContact, SNMPv2-MIB) : Siemens AG
    2013-06-23 23:39:56,684 Registered OID (1, 3, 6, 1, 2, 1, 1, 5) instance (0,) (sysName, SNMPv2-MIB) : CP 443-1 EX40
    2013-06-23 23:39:56,684 Registered OID (1, 3, 6, 1, 2, 1, 1, 6) instance (0,) (sysLocation, SNMPv2-MIB) :
    2013-06-23 23:39:56,684 Registered OID (1, 3, 6, 1, 2, 1, 1, 7) instance (0,) (sysServices, SNMPv2-MIB) : 72
    2013-06-23 23:39:56,685 SNMP server started on: ('0.0.0.0', 161)
    2013-06-23 23:39:56,685 HTTP server started on: ('0.0.0.0', 80)

