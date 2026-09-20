CPU stop and restart probes
===========================

Conpot answers common ICS scanner probes that try to stop or restart a PLC
CPU. The reply is protocol-correct and a session event is logged. The
listening process itself is **never** stopped.

=======================  ===========================================  ==================
Probe                    Where it is enabled                          Session event
=======================  ===========================================  ==================
Modbus function 90 UMAS  ``plc_modbus`` (``<umas enabled="true"/>``)  ``UMAS_START`` / ``UMAS_STOP``
S7comm job ``0x29`` / ``0x28``  ``default`` s7comm                     ``PLC_STOP`` / ``PLC_START``
EtherNet/IP encapsulation NOP (``0x0000``)  ``default`` enip          ``ENIP_NOP``
=======================  ===========================================  ==================

The default Modbus profile stays Siemens-flavored and rejects function 90
with an illegal-function exception. Enable UMAS only on profiles that
should look like Schneider Modicon (as ``plc_modbus`` does).

Automated tests
---------------

From a source checkout::

    uv run pytest \
      conpot/tests/test_modbus_server.py::TestModbusUmas \
      conpot/tests/test_modbus_server.py::TestModbusServer::test_umas_disabled_is_illegal_function \
      conpot/tests/test_s7_server.py::TestS7Server::test_plc_stop_is_ack_data \
      conpot/tests/test_s7_server.py::TestS7Server::test_plc_start_is_ack_data \
      conpot/tests/test_enip_server.py::TestENIPServer::test_send_nop \
      -q

Or the full protocol suites::

    uv run pytest \
      conpot/tests/test_modbus_server.py \
      conpot/tests/test_s7_server.py \
      conpot/tests/test_enip_server.py \
      -q

Manual test: Modbus UMAS (function 90)
--------------------------------------

Start the Schneider-flavored profile (Modbus on TCP **5020**, unit ID **1**)::

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

Manual test: S7comm CPU stop / start
------------------------------------

Start the default profile (S7comm on TCP **10201**)::

    uv run conpot --template default -f

In another terminal, use the in-tree helper (same client as the tests)::

    uv run python

.. code-block:: python

    from conpot.tests.helpers import s7comm_client

    host, port = "127.0.0.1", 10201
    con = s7comm_client.s7(host, port, src_tsap=0x100, dst_tsap=0x102)
    con.Connect()

    stop = con.plc_stop_function()
    print("stop pdu_type", stop.type, "error", stop.error, "params", stop.parameters.hex())
    # expect pdu_type 3 (Ack-Data), error 0, params 29

    start = con.plc_start_function(b"WARM_START")
    print("start pdu_type", start.type, "error", start.error, "params", start.parameters.hex())
    # expect pdu_type 3, error 0, params 28

    con.s.close()

Logs should show ``PLC_STOP`` then ``PLC_START``. The S7 listener keeps
serving; only the emulated CPU flag flips.

Manual test: EtherNet/IP NOP
----------------------------

Start the default profile (ENIP on TCP **44818**)::

    uv run conpot --template default -f

NOP is encapsulation command ``0x0000``. The peer must **not** get a
reply; a later List Identity on the same socket must still work::

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
uses TCP).
