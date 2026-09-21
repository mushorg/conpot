OPC UA
======

The ``opcua`` template emulates an **OPC UA** (IEC 62541) server over
``opc.tcp`` on port **4840**. Conpot owns TCP accept, idle timeouts, and
attack-session logging; protocol PDUs and the address space are handled by
`asyncua <https://pypi.org/project/asyncua/>`_ (``UaProcessor`` /
``InternalServer``). ``BinaryServer`` is not used.

This is a honeypot subset for scanners and clients — SecurityPolicy **None**
only. FileType transfer capture, Sign/Encrypt, and proxying to a live PLC are
out of scope; see GitHub issue `#82`.

``asyncua`` is licensed LGPL-3+. That is an explicit maintainer tradeoff with
Conpot's GPL-2.0-only license.

Start the server
----------------

OPC UA-only profile::

    uv run conpot --template opcua -f

You should see OPCUAServer listening on ``0.0.0.0:4840``. Port 4840 does not
require root.

Template configuration
----------------------

``opcua.toml`` is validated by the ``opcua`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 14 58

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:4840``)
   * - ``timeout``
     - ``5``
     - Idle read timeout in seconds (scanners that RST or hang)
   * - ``endpoint_path``
     - ``/conpot/server/``
     - Path component of the ``opc.tcp`` endpoint URL
   * - ``server_name``
     - ``Conpot OPC UA Server``
     - Application name advertised to clients
   * - ``namespace_uri``
     - ``http://conpot.org/OPCUA/``
     - Custom namespace for Plant variables
   * - ``application_uri``
     - ``urn:conpot:opcua``
     - Application URI
   * - ``variables``
     - —
     - Address-space variables (``name``, ``type``, ``value``)

If ``variables`` is empty, the server seeds ``Temperature = 25.0``. Concurrent
TCP clients share one ``InternalServer`` address space.

Shipped variables (``opcua`` template)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 12 16

   * - Name
     - Type
     - Initial value
   * - Temperature
     - float
     - ``25.0``
   * - Pressure
     - float
     - ``101.3``
   * - PumpRunning
     - boolean
     - ``true``
   * - BatchId
     - integer
     - ``42``

Example excerpt::

    [opcua]
    enabled = true
    host = "0.0.0.0"
    port = 4840
    timeout = 5
    endpoint_path = "/conpot/server/"
    server_name = "Conpot OPC UA Server"

    [[opcua.variables]]
    name = "Temperature"
    type = "float"
    value = 25.0

Session events
--------------

Each TCP client gets an attack session. Typical ``event_type`` values:

* ``NEW_CONNECTION`` / ``CONNECTION_LOST`` — connect and cleanup
* ``REQUEST`` — Hello, OpenSecureChannel, CreateSession, Read, Browse, …

Idle sockets time out after ``timeout`` seconds so banner scans do not leave
sessions hung open.

Automated tests
---------------

::

    uv run pytest conpot/tests/test_opcua_server.py -q

The suite covers connection logging, reading template variables with an
asyncua client, concurrent clients, and peer RST cleanup.

Manual test: read a variable
----------------------------

With the ``opcua`` template running, in another terminal::

    uv run python

.. code-block:: python

    import asyncio
    from asyncua import Client

    async def main():
        url = "opc.tcp://127.0.0.1:4840/conpot/server/"
        async with Client(url=url) as client:
            idx = await client.get_namespace_index("http://conpot.org/OPCUA/")
            plant = await client.nodes.objects.get_child([f"{idx}:Plant"])
            temp = await plant.get_child([f"{idx}:Temperature"])
            print(await temp.read_value())  # 25.0

    asyncio.run(main())

Logs should include ``NEW_CONNECTION``, ``REQUEST``, and ``CONNECTION_LOST``
when the client disconnects.
