OPC UA
======

The ``opcua`` template emulates an **OPC UA** (IEC 62541) server over
``opc.tcp`` on port **4840**. Conpot owns TCP accept, idle timeouts, and
attack-session logging; protocol PDUs and the address space are handled by
`asyncua <https://pypi.org/project/asyncua/>`_ (``UaProcessor`` /
``InternalServer``). ``BinaryServer`` is not used.

This is a honeypot subset for scanners and clients — SecurityPolicy **None**
only. Sign/Encrypt and proxying to a live PLC are out of scope (see GitHub
issue `#82`). File transfer capture via standard OPC UA **FileType** objects
is supported (see GitHub issue `#651`).

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
   * - ``files``
     - —
     - Address-space FileType nodes (``name``, ``content``, ``writable``, ``mime_type``)
   * - ``opcua_root_path``
     - ``/data/opcua/``
     - Subdirectory within Conpot VFS for OPC UA files
   * - ``add_src``
     - —
     - Optional host directory path to mirror files into VFS
   * - ``data_fs_subdir``
     - ``opcua``
     - Subdirectory under ``data_fs`` where uploaded payloads are captured
   * - ``max_file_size``
     - ``1048576``
     - Maximum allowed uploaded payload size in bytes (1 MB)
   * - ``max_handles_per_session``
     - ``16``
     - Maximum concurrent open FileType handles per attack session
   * - ``max_handles_total``
     - ``100``
     - Maximum concurrent open FileType handles per file node

If ``variables`` is empty, the server seeds ``Temperature = 25.0``. If ``files``
is empty, the server seeds decoy ``firmware.bin`` and ``configuration.xml``
FileType nodes. Concurrent TCP clients share one ``InternalServer`` address space.

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

    [[opcua.files]]
    name = "firmware.bin"
    content = "CONPOT_PLC_FW_V2.1.0"
    writable = true
    mime_type = "application/octet-stream"

Session events
--------------

Each TCP client gets an attack session. Typical ``event_type`` values:

* ``NEW_CONNECTION`` / ``CONNECTION_LOST`` — connect and cleanup
* ``REQUEST`` — Hello, OpenSecureChannel, CreateSession, Read, Browse, Call, …
* ``OPCUA_FILE_OPEN`` / ``OPCUA_FILE_CLOSE`` — FileType Open / Close invocations
* ``OPCUA_FILE_READ`` / ``OPCUA_FILE_WRITE`` — File transfer reads and writes
* ``OPCUA_FILE_CAPTURED`` — Logged upon write finalization, including payload ``size``, ``md5``, and saved ``path``

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
