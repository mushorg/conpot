HTTP
====

The default template listens on TCP **8800**.

Template configuration
----------------------

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
