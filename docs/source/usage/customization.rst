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

The ``<device_info />`` section allows to define the device info returned to a Modbus 43 function call.

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

HTTP
~~~~

In the ``<http>`` section, you may configure the characteristics of the web server we designed for conpot, as well
as each website and resource with its respective headers and behaviour. Last but not least, you can also control how
and when error codes and their respective error pages are delivered.

Let us talk about the global http configuration first:

.. code-block:: xml

    <global>
        <config>
            <!-- what protocol shall we use by default? -->
            <entity name="protocol_version">HTTP/1.1</entity>
            <!-- if we find any date header to be delivered, should we update it to a real value? -->
            <entity name="update_header_date">true</entity>
            <!-- should we disable the HTTP HEAD method? -->
            <entity name="disable_method_head">false</entity>
            <!-- should we disable the HTTP TRACE method? -->
            <entity name="disable_method_trace">false</entity>
            <!-- should we disable the HTTP OPTIONS method? -->
            <entity name="disable_method_options">false</entity>
            <!-- TARPIT: how much latency should we introduce to any response by default? -->
            <entity name="tarpit">0</entity>
        </config>

        <!-- these headers will be sent with each response -->
        <headers>
            <!-- this date header will be updated, if enabled above -->
            <entity name="Date">Sat, 28 Apr 1984 07:30:00 GMT</entity>
        </headers>
    </global>

The comments along with each configuration item should provide enough information to understand what its actually
doing. Use the ``disable_method`` items to reflect the features actually provided by the real thing you're trying
to resemble. If you choose to disable the ``update_server_date`` feature, the ``Date`` header will remain untouched
and deliver a static response each time a website is requested.

The ``headers`` section found within the ``global`` configuration stanza is added to each and every page that is being
delivered. Though, it will be overwritten by headers defined for individual resources if they are featuring the same
header name.

The ``tarpit`` section slows down the delivery of the web page. This is used to simulate slower devices that would not
deliver websites in a fraction of a second. The tarpit value should be specified in seconds and milliseconds, using one
or two floats. A single float, e.g. "3.5", would introduce 3.5 seconds of delay before the requested page is delivered
to the browser. A pair of floats separated by a semikolon, e.g. "0.1;1.2", would introduce a random delay between 0.1
and 1.2 seconds, that is randomized every time the resource is requested.

Let us head over to the htdocs area:

.. code-block:: xml

    <!-- how should the different URI requests be handled -->
    <htdocs>
        <node name="/">
            <!-- force response status code to 302 -->
            <status>302</status>
            <headers>
                <!-- these headers will be sent along with this response -->
                <entity name="Content-Type">text/html</entity>
                <entity name="Location">/index.html</entity>
            </headers>
        </node>
    </htdocs>

Here we do all the configuration that allows conpot to deliver individual files. The HTTP engine will never try to
deliver a file that is not defined by a <node name="$filename"> stanza, resulting in additional security against
directory traversal attempts etc.

The example above shows the entry point, which is requested by web browsers if just the domain or ip address, but no
web page has been specified by the user (Example: http://www.my-honeypot.com/ ).

Node names must be specified using absolute paths, starting from the web root ( "/" ). By default, requests that can
be served because they address paths specified here, will be answered with status code 200 (OK). If you want to return
an individual status code, you can use the ``<status>$statuscode</status>`` configuration item. The example above shows
the usage of status 302, which redirects the browser to another resource. In our case, this is "/index.html".

All headers found within the ``<headers>`` section are appended to the headers found in the headers section we
defined in the global configuration block before. As mentioned before, duplicated header will be replaced with the
most specific one.

Requests for resources that are not specified within the XML, as well as requests that are specified but can not be
handled since the respective file can not be found within the template folder on the filesystem, will be answered with
a 404 (Not found) status response.

.. code-block:: xml

    <node name="/index.html">
        <!-- this tarpit will override the globally set tarpit for this node -->
        <tarpit>0.0;0.3</tarpit>
        <headers>
            <entity name="Last-Modified">Tue, 19 May 1993 09:00:00 GMT</entity>
            <entity name="Content-Type">text/html</entity>
            <entity name="Set-cookie">path=/</entity>
        </headers>
    </node>

The root node ( "/" ) instructed the browser to redirect the user to "/index.html". This configuration stanza shows
few entities we already know, along with an additional ``<tarpit>`` item, which works the same way as the tarpit entity
from the global section and replaces the global tarpit for this resource.

.. code-block:: xml

    <node name="/index.htm">
        <!-- this node will inherit the payload from the referenced alias node without telling the browser -->
        <alias>/index.html</alias>
    </node>

For added flexibility, we also introduced a way to configure aliases. Using the comfort of aliases, you can instruct
conpot to act on behalf of another (already configured) resource without needing to define all the configuration items
again. The example above uses the alias feature to answer to requests for "/index.htm", even though the real resource
name is "/index.html".

Please note that the browser will not be aware of this internal translation, since the alias is resolved by conpot
itself. Further, you can't point to another alias, since (to prevent recursions) only one alias-level is being resolved.

.. code-block:: xml

    <node name="/some_chunked_file.html">
        <!-- this feature controls chunked transfer encoding -->
        <chunks>130,15,30,110</chunks>
    </node>

Dynamic pages are often delivered using chunked transfer encoding rather than content length encoding since the web
server might not know how big the actual content he delivers might get while dynamic content is being created. The
``<chunks>`` directive enables chunked transfer encoding, delivering the website in several parts instead of a whole
big stream of data.

The configuration above shows a page that is delivered in 4 chunks which are 130, 15, 30 and 110 bytes in size. If you
happen to specify too less bytes and the page to be delivered happens to be larger than what you configured, conpot will
not truncate your file but append a final chunk that includes all the missing bytes that complete the request.

Chunks are sent subsequently, at the moment there is no tarpit applied between them.

.. code-block:: xml

    <statuscodes>
        <status name="400">
                <!-- 400 (BAD REQUEST) errors should be super fast and responsive -->
                <tarpit>0</tarpit>
                <entity name="Content-Type">text/html</entity>
        </status>
    </statuscodes>

Status codes are specified the same way like htdocs, but instead of their absolute path, the status code itself is
used to identify the resource. Status codes support all the features we know from the htdocs described before, but they
can not be aliased to htdocs and vice versa.

.. code-block:: xml

    <node name="/redirected-page">
        <!-- this page is redirected to another web server -->
        <proxy>10.0.0.100</proxy>
    </node>

Requests to this page / resource will be forwarded to another webserver. Since conpot spawns the request to this
webserver, the feature is similar to a backproxy - the web browser will not notice any difference since conpot delivers
the resulting web page to the requesting client on behalf of the server that generated the content in first place.

This feature can also be applied to status codes. For example, if the proxy directive is applied to status code 404
(Not Found), all requests that can not be handled by conpot itself are secretly forwarded to another system, which might
be the real device for higher interaction setups. If no resources other than the 404 status, are configured, this
results in each and every request to be forwarded to the other webserver on behalf of the client. This way, conpot can
act similar to a terminating honeywall in higher interaction setups for the HTTP protocol.