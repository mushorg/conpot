SNMP
====

The default template listens on UDP **16100**.

Template configuration
----------------------

In the ``<snmp />`` section you define a management information base (MIB). Each ``<symbol>`` has a name
attribute and a ``<value>`` child. The text of ``<value>`` is a **databus key**, not a literal payload.
Conpot resolves that key from the template's ``<databus>`` / ``<key_value_mappings>`` section at startup.
If the key is missing, SNMP fails to start with an ``AssertionError``.

Define the payload on the databus first (in ``template.toml`` ):

.. code-block:: toml

    SystemDescription = "Siemens, SIMATIC, S7-200"

.. code-block:: xml

    <key name="SystemDescription">
        <value type="value">"Siemens, SIMATIC, S7-200"</value>
    </key>

Then reference the key from ``snmp.xml``:

.. code-block:: xml

    <symbol name="sysDescr">
        <!-- Value is key in databus -->
        <value>SystemDescription</value>
    </symbol>

To include other MIBs, place the ASN.1 sources under ``templates/<template>/snmp/mibs/``.
PySNMP compiles them on demand (standard MIB dependencies can also be fetched remotely).
Optionally set a cache directory with ``--mibcache``.

As an example, add ``ifNumber`` from IF-MIB. First define the databus key:

.. code-block:: xml

    <key name="ifNumber">
        <value type="value">2</value>
    </key>

Then wire it in the SNMP template:

.. code-block:: xml

            <mib name="IF-MIB">
                <symbol name="ifNumber">
                    <value>ifNumber</value>
                </symbol>
            </mib>

Related symbols that need several instances of a single OID use the ``instance`` attribute.
Each instance still points at a databus key:

.. code-block:: xml

            <mib name="IF-MIB">
                <symbol name="ifDescr" instance="1">
                    <value>ifDescr1</value>
                </symbol>

                <symbol name="ifDescr" instance="2">
                    <value>ifDescr2</value>
                </symbol>
            </mib>

If ``instance`` is omitted, the default instance ``(0,)`` is assumed.

Dynamic values also come from the databus. Use ``type="function"`` to point at a Python class
(or other callable) instead of a static value. The default template uses this for sysUpTime:

.. code-block:: xml

    <key name="Uptime">
        <value type="function">conpot.emulators.misc.uptime.Uptime</value>
    </key>

.. code-block:: xml

            <mib name="SNMPv2-MIB">
                <symbol name="sysUpTime">
                    <value>Uptime</value>
                </symbol>
            </mib>

``Uptime`` returns seconds since Conpot started (or since an optional constructor start time).
For other dynamic behaviour, add your own emulator class and register it the same way on the databus.

The SNMP interface can be configured to adjust its behaviour by adding the corresponding configuration directives to
the ``config`` area inside the ``snmp`` block:

.. code-block:: xml

        <config>
            <!-- Configure individual delays for SNMP commands -->
            <entity name="tarpit" command="get">0.1;0.2</entity>
            <entity name="tarpit" command="set">0.1;0.2</entity>
            <entity name="tarpit" command="next">0.0;0.1</entity>
            <entity name="tarpit" command="bulk">0.2;0.4</entity>

            <!-- Configure DoS evasion thresholds (req_per_ip/minute;req_overall/minute) -->
            <entity name="evasion" command="get">120;240</entity>
            <entity name="evasion" command="set">120;240</entity>
            <entity name="evasion" command="next">240;600</entity>
            <entity name="evasion" command="bulk">120;240</entity>
        </config>

The ``tarpit`` section slows down the delivery of SNMP responses. This is used to simulate slower devices that would not
respond to SNMP requests in a fraction of a second. The tarpit value should be specified in seconds and milliseconds,
using one or two floats. A single float, e.g. "3.5", would introduce 3.5 seconds of delay before the requested OID is
delivered to the client. A pair of floats separated by a semikolon, e.g. "0.1;1.2", would introduce a random delay
between 0.1 and 1.2 seconds, that is randomized every time an OID is requested.

Tarpits are configured individually for each type of request (get, set, next, bulk). If the corresponding request type
is not configured, answers are generated instantly.

The ``evasion`` feature is used for security reasons. Due to the fact that SNMP uses UDP for transport, it is prone to
address spoofing. Since SNMP responds to rather small requests with responses that contain bigger payloads, conpot
could be used as a relay for traffic amplification attacks.

In order to avoid (or at least mitigate) such attacks, the evasion feature has been introduced. For each request type
an individual threshold can be applied, consisting of two integers which are separated by a semikolon. As an example,
the evasion value "100:200" for ``get`` requests results in the following restrictions to be applied:

* First Integer (100)
    Specifies the number of requests allowed per IP per minute. As soon as the number of requests / ip within 60 seconds
    exceeds the configured amount (e.g. 100), all subsequent requests will be discarded until the number of requests
    by this IP address drops under the limit.
* Second Integer (200)
    Specifies the number of requests allowed overall / minute. "Overall" in this context means: Requests of the
    respective command. In this example, as soon as the total number of ``get`` requests within 60 seconds exceeds the
    configured amount (e.g. 200), all subsequent get requests, regardless of the senders IP address, will be discarded
    until the number of get requests drops under the limit.

Keep in mind that snmpwalks are in fact a large number of ``next`` requests, while ``bulk`` requests may contain several
answers within one reply. Therefore, the evasion limits for ``next`` should be chosen more generous while the limits for
``bulk`` requests should be kept rather conservative due to its risk of being abused for traffic amp attacks.
