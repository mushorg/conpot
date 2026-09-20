Modbus
======

The default and ``plc_modbus`` templates listen on TCP **5020**. Configuration
lives in ``modbus.xml``; process values live on the databus (see
:doc:`../concepts/databus`).

Template configuration
----------------------

The ``<device_info />`` section defines the device info returned to a Modbus 43
function call.

The ``<slave />`` section defines **internal** Modbus slaves. Each slave is a
databus-backed memory map (``<blocks />``) addressed by its ``id`` (Modbus unit
id). Conpot never forwards requests to an external PLC; every unit id you
configure is served from the template.

``mode`` selects addressing semantics:

* ``tcp`` — any configured unit id (including ``255``, the usual Modbus/TCP
  “this device” address) is served from the matching internal slave.
* ``serial`` — unit id ``0`` is treated as a serial-line broadcast (no
  response); ids ``1``–``247`` address internal slaves.

A binary output block has the type ``COILS``, binary input blocks
``DISCRETE_INPUTS``. ``ANALOG_INPUTS`` and ``HOLDING_REGISTERS`` hold 16-bit
register values. You define the starting address and size.

The block ``name`` attribute is the **databus key**. Payload lives in
``template.toml`` / ``template.xml``, not inline in ``modbus.xml``.
``<content>`` is documentation only; the Python handler never reads it.

.. code-block:: xml

    <block name="memoryModbusSlave1BlockA">
        <type>COILS</type>
        <starting_address>1</starting_address>
        <size>8</size>
        <content>memoryModbusSlave1BlockA</content>
    </block>

Initialize that key as a list on the databus (evaluated once at startup):

.. code-block:: xml

    <key name="memoryModbusSlave1BlockA">
        <value type="value">[0 for b in range(0,8)]</value>
    </key>

The ``plc_modbus`` profile wires those lists to a scan cycle so coil writes
produce changing discrete inputs, holding registers, and analog inputs.
See :doc:`../usage/plc_emulator` for how the emulator works, how to configure
it, and how to test it. The default template still uses static
(randomized-once) lists and is unchanged.

``HOLDING_REGISTERS`` are writable working registers. In ``plc_modbus``,
holding register 0 is incremented by the native engine while the plant is
running.

Example with several internal slaves (each ``id`` is a distinct unit id):

.. code-block:: xml

    <mode>tcp</mode>
    <slaves>
        <slave id="1">
            <blocks>
                <!-- coils / registers for unit id 1 -->
            </blocks>
        </slave>
        <slave id="2">
            <blocks>
                <!-- independent memory map for unit id 2 -->
            </blocks>
        </slave>
        <slave id="255">
            <blocks>
                <!-- conventional Modbus/TCP “this device” unit id -->
            </blocks>
        </slave>
    </slaves>

Schneider UMAS (function 90)
----------------------------

Optional Schneider UMAS is controlled by ``<umas enabled="true"/>``. When
enabled, UMAS start (``0x40``) and stop (``0x41``) return status ``0xFE`` and
log ``UMAS_START`` / ``UMAS_STOP``. Other UMAS codes return ``0xFD``. Leave it
off on Siemens-flavored profiles. ``plc_modbus`` turns it on and sets
``device_info`` to a Modicon identity.

The default Modbus profile stays Siemens-flavored and rejects function 90 with
an illegal-function exception. The listening process itself is **never**
stopped.

Automated tests::

    uv run pytest \
      conpot/tests/test_modbus_server.py::TestModbusUmas \
      conpot/tests/test_modbus_server.py::TestModbusServer::test_umas_disabled_is_illegal_function \
      -q

Manual test: start the Schneider-flavored profile (unit ID **1**)::

    uv run conpot --template plc_modbus -f

In another terminal::

    uv run python

.. code-block:: python

    import socket
    import struct

    def exchange(pdu, host="127.0.0.1", port=5020, unit=1):
        header = struct.pack(">HHHB", 0, 0, len(pdu) + 1, unit)
        with socket.create_connection((host, port), timeout=2) as s:
            s.sendall(header + pdu)
            return s.recv(1024)

    # stop: function 0x5A, session 0x01, UMAS 0x41
    print(exchange(b"\x5a\x01\x41\xff\x00").hex())
    # expect ... 5a01fe  (status 0xFE)

    # start: UMAS 0x40
    print(exchange(b"\x5a\x00\x40").hex())
    # expect ... 5a00fe

    # other UMAS code → status 0xFD
    print(exchange(b"\x5a\x00\x02").hex())
    # expect ... 5a00fd

Conpot logs should include ``UMAS_STOP`` / ``UMAS_START``. Against the
``default`` template the same stop frame returns exception ``DA 01``
(illegal function).

To enable UMAS on a custom Modbus template, set a Schneider-style
``device_info`` and add::

    <umas enabled="true"/>

Related probes on S7comm and EtherNet/IP: :doc:`../usage/stop_restart`.
