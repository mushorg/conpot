=============
Customization
=============

The default profile
-------------------

Conpot is shipped with a default profile(``default.xml``) which provides basic emulation of a
`Siemens S7-200 CPU <https://www.automation.siemens.com/mcms/programmable-logic-controller/en/simatic-s7-controller/s7-200/pages/default.aspx?HTTPS=REDIR>`_
with a few expansion modules installed. The attack surface of the default emulation includes the Modbus and SNMP protocols.

Modbus
~~~~~~

The ``<slave />`` section allows you to define the slaves. Every slave definition is separated into ``<blocks />``.

An binary output block has the type ``COILS``, binary input blocks ``DISCRETE_INPUTS``. You define the starting address
and size. ``ANALOG_INPUTS`` hold data in byte size.

In the ``<values />`` section you take the starting address and fill the field with values. The content is evaluated so
you can easily fill it with random values.

.. code-block:: xml

    <block name="a">
        <!-- COILS/DISCRETE_OUTPUTS aka. binary output, power on/power off
             Here we map modbus addresses 1 to 127 to S7-200 PLC Addresses Q0.0 to Q15.7 -->
        <type>COILS</type>
        <starting_address>1</starting_address>
        <size>128</size>
        <values>
            <value>
                <address>1</address>
                <!-- Will be parsed with eval() -->
                <content>[random.randint(0,1) for b in range(0,128)]</content>
            </value>
        </values>
    </block>

``HOLDING_REGISTERS`` can be considered as temporary data storage. You define them with the starting address and their
size. Holding registers don't have any initial value.

SNMP
~~~~

In the ``<snmp />`` section you define a management information base (MIB). MIBs consist of a ``<symbol>`` with a name
attribute, and its ``<value>``.

.. code-block:: xml

    <symbol name="sysDescr">
        <value>Siemens, SIMATIC, S7-200</value>
    </symbol>

In the following example we will show how to include other MIBs. As an example we will add the ifNumber symbol from
the IF-MIB.
First we have to download the IF-MIB and also the IANAifType-MIB since IF-MIB depends on this::

    wget http://www.iana.org/assignments/ianaiftype-mib/ianaiftype-mib
    wget ftp://ftp.cisco.com/pub/mibs/v2/IF-MIB.my

Then compile the MIBs to python code::

    build-pysnmp-mib IF-MIB.my > IF-MIB.py
    build-pysnmp-mib ianaiftype-mib > IANAifType-MIB.py

Finally add your custom snmp configuration to the template:

.. code-block:: xml

            <mib name="IF-MIB">
                <symbol name="ifNumber">
                    <value>2</value>
                </symbol>
            </mib>
