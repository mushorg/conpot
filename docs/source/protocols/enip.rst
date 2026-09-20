EtherNet/IP (ENIP)
==================

The default template listens for EtherNet/IP encapsulation on TCP
**44818** (UDP when ``<mode>udp</mode>`` in ``enip.xml``). Device identity
and tags come from ``conpot/templates/default/enip.xml``.

Start the server
----------------

Full honeypot (recommended for manual probes)::

    uv run conpot --template default -f

You should see ENIP started on ``0.0.0.0:44818``. Port 44818 does not
require root.

ENIP only (dev helper; binds **60002** by default)::

    uv run python tools/start_protocol.py enip

Automated tests
---------------

::

    uv run pytest conpot/tests/test_enip_server.py -q

The suite covers List Services / Identity / Interfaces (TCP and UDP),
Get/Set Attribute Single on tag ``22/1/1``, NOP keepalive, and a
malformed TCP frame.

Manual test: in-tree client
---------------------------

``conpot.tests.helpers.enip_client.EnipClient`` is the same blocking
client the pytest suite uses. With Conpot running on the default port,
in another terminal::

    uv run python

.. code-block:: python

    import struct
    from conpot.tests.helpers.enip_client import EnipClient

    host, port = "127.0.0.1", 44818

    with EnipClient(host, port, timeout=4.0) as client:
        print(client.list_services())
        # Communications

        print(client.list_identity())
        # product_name 1756-L61/B LOGIX5561, vendor_id 1, ...

        data = client.get_attribute_single(22, 1, 1)
        print("SCADA tag", struct.unpack_from("<b", data)[0])
        # 100

        client.set_attribute_single(22, 1, 1, struct.pack("<b", 50))
        data = client.get_attribute_single(22, 1, 1)
        print("after write", struct.unpack_from("<b", data)[0])
        # 50

One-shot List Identity from the shell::

    uv run python -c "
    from conpot.tests.helpers.enip_client import EnipClient
    with EnipClient('127.0.0.1', 44818, timeout=4.0) as c:
        print(c.list_identity())
    "

Against ``tools/start_protocol.py enip``, use port **60002** instead of
44818. For UDP mode, pass ``udp=True`` to ``EnipClient`` (and set the
template ``<mode>`` to ``udp``).

Default tags (``addr`` is class/instance/attribute)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 16 16 16 24

   * - Name
     - Type
     - Addr
     - Initial value
   * - SCADA
     - SINT
     - 22/1/1
     - 100
   * - TEXT
     - SSTRING
     - 22/1/2
     - A
   * - FLOAT
     - REAL
     - 22/1/3
     - 0.1

Manual test: nmap ``enip-info``
-------------------------------

nmap's ``enip-info`` script sends List Identity and prints vendor,
product name, serial, and revision. Against the default **TCP** listener::

    nmap -Pn -p 44818 --script enip-info 127.0.0.1

Expect something like ``productName: 1756-L61/B LOGIX5561`` and
``vendor: Rockwell Automation/Allen-Bradley (1)``.

If you switch the template to UDP, probe with::

    nmap -Pn -sU -p 44818 --script enip-info 127.0.0.1

Manual test: encapsulation NOP
------------------------------

NOP (encapsulation command ``0x0000``) must produce **no** reply; a later
List Identity on the same TCP socket must still work. Session event:
``ENIP_NOP``. The listening process is never stopped.

Start the default profile, then::

    uv run python

.. code-block:: python

    import socket
    import struct

    host, port = "127.0.0.1", 44818
    nop = struct.pack("<HHII8sI", 0, 0, 0, 0, b"\x00" * 8, 0)
    identity = struct.pack("<HHII8sI", 0x0063, 0, 0, 0, b"\x00" * 8, 0)

    with socket.create_connection((host, port), timeout=2) as s:
        s.sendall(nop)
        s.settimeout(0.5)
        try:
            print("unexpected reply", s.recv(1024).hex())
        except TimeoutError:
            print("NOP: no reply (ok)")
        s.settimeout(2)
        s.sendall(identity)
        reply = s.recv(1024)
        print("list_identity cmd", hex(struct.unpack_from("<H", reply)[0]), "len", len(reply))

Logs should include ``ENIP_NOP``. The same check works over UDP on the
same port when the template's ENIP mode is UDP (the default template
uses TCP). Related stop/restart probes on other protocols:
:doc:`../usage/stop_restart`.
