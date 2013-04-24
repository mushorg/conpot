Using Conpot
============

Creating custom profiles
------------------------

Conpot comes with a ``default.xml`` profile in the templates directory.

Modbus template
~~~~~~~~~~~~~~~

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

SNMP template
~~~~~~~~~~~~~

In the ``<snmp />`` section you define a management information base (MIB). MIBs consist of a ``<symbol>`` with a name
attribute, and its ``<value>``.

.. code-block:: xml

    <symbol name="sysDescr">
        <value>Siemens, SIMATIC, S7-200</value>
    </symbol>