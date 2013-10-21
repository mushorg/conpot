=============
Customization
=============

The default profile
-------------------

Conpot is shipped with a default profile(``default.xml``) which provides basic emulation of a
`Siemens S7-200 CPU <https://www.automation.siemens.com/mcms/programmable-logic-controller/en/simatic-s7-controller/s7-200/pages/default.aspx?HTTPS=REDIR>`_
with a few expansion modules installed. The attack surface of the default emulation includes the protocols MODBUS, HTTP,
SNMP and s7comm.

While most of the configuration takes place within the XML profile, some parts are kept in seperate folders within the
templates directory to avoid clutter.


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

Conpot will compile the MIB files automatically, but unless the MIB files are places in the current work directory, you
need to provide a path to the files using the '-a' parameter (The path will be searched recursively for MIB files).::

    sudo conpot -t my_custom_template.xml -a /opt/mymibs

Finally add your custom snmp configuration to the template:

.. code-block:: xml

            <mib name="IF-MIB">
                <symbol name="ifNumber">
                    <value>2</value>
                </symbol>
            </mib>

The value of the ifNumber symbol (2) implies that there is more than one interface - therefore there might be related
symbols that need identifiers to initialize several instances of a single symbol. To apply an instance id, add the
"instance" attribute to the symbol. Example:

.. code-block:: xml

            <mib name="IF-MIB">
                <symbol name="ifDescr" instance="1">
                    <value>This is the first interface</value>
                </symbol>

                <symbol name="ifDescr" instance="2">
                    <value>This is the second interface</value>
                </symbol>
            </mib>

If not specified, the default instance (0) is being assumed.

Several symbols feature dynamic values. Conpot can be instructed to deliver dynamic content by adding the engine
definition to the template. Example:

.. code-block:: xml

            <mib name="SNMPv2-MIB">
                <symbol name="sysUpTime">
                    <value>0</value>
                    <engine type="sysuptime"></engine>
                </symbol>
            </mib>

The example above always responds with the time in milliseconds since conpot was initialized.

Currently, the following engine types are implemented:

* increment
    Increments the value each time it is requested. Default incrementor: 1, resetting to initial value at 2147483647.
    Modified example:    <engine type="increment">1:100</engine>    ( => increment by 1, reset at 100 )

* decrement
    Decrements the value each time it is requested. Default decrementor: 1, resetting to initial value at -2147483648.
    Modified example:    <engine type="decrement">1:0</engine>    ( => decrement by 1, reset at 0 )

* randominc
    Randomly increments the value each time it is requested. Default incrementor range: 1-65535,
    resetting to initial value at 2147418112.
    Modified example:    <engine type="randominc">1:100:999</engine>    ( => increment by rand(1,100), reset at 999 )

* randomdec
    Randomly decrements the value each time it is requested. Default decrementor range: 1-65535,
    resetting to initial value at -2147418113.
    Modified example:    <engine type="randomdec">1:100:-999</engine>    ( => increment by rand(1,100), reset at -999 )

* randomint
    Randomly assigns an integer. Default range: 1-65535.
    Modified example:    <engine type="randomint">1:100</engine>    ( => assign a random integer between 1 and 100 )

* sysuptime
    Assigns the current uptime of the conpot process measured in milliseconds.
    Modified example:    <engine type="sysuptime"></engine>    ( => additional value will be used as a head-start )

* evaluate
    Assigns the result of value evaluated as python code ( eval ).
    Modified example:    <engine type="evaluate">random.randrange(0,100,10)</engine>    ( => assign a random int between 0 and 100 in steps of 10 )

* static
    Do not assign any value. This is default of no <engine> field is supplied and will always deliver the initial value.
