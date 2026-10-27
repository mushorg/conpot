S7comm
======

The default template listens for S7comm on TCP **10201**.

CPU stop and start
------------------

Conpot answers S7comm job ``0x29`` (stop) and ``0x28`` (start) with a
protocol-correct Ack-Data reply and logs ``PLC_STOP`` / ``PLC_START``. The
listening process itself is **never** stopped; only the emulated CPU flag
flips.

Automated tests::

    uv run pytest \
      conpot/tests/test_s7_server.py::TestS7Server::test_plc_stop_is_ack_data \
      conpot/tests/test_s7_server.py::TestS7Server::test_plc_start_is_ack_data \
      -q

Manual test: start the default profile::

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

Logs should show ``PLC_STOP`` then ``PLC_START``.

Module identification (SZL)
---------------------------

Conpot answers the Read SZL requests that scanners such as nmap's
``s7-info`` and plcscan use for device identification:

* ``0x0011`` returns all module identification records (module, basic
  hardware, basic firmware, boot loader), whatever index is requested.
* ``0x0111`` returns the single record selected by the index (1, 6, 7 or
  0x81).
* ``0x001C`` returns the component identification records.

The values come from the databus keys named in ``s7comm.toml`` under
``W#16#xy11`` and ``W#16#xy1C``. For ``W#16#xy11``:

* ``W#16#0001`` and ``W#16#0006`` hold an order number (MLFB, up to 20
  characters, e.g. ``6ES7 315-2EH14-0AB0``). An optional ``version`` key
  names a databus value with the two hardware version words, e.g. ``3.1``.
* ``W#16#0007`` holds the firmware version, e.g. ``V3.2.8``.
* ``W#16#0081`` holds the boot loader version, e.g. ``A32.9.9``. Leave the
  item out to omit the record.

Versions are sent as the letter followed by binary major, minor and patch
numbers. With a real CPU's values, the reply matches a CPU 315-2 PN/DP
byte for byte (see ``test_szl_0011_matches_real_cpu_315_2_pn_dp``).

Check a running instance with::

    nmap -Pn -p 102 --script s7-info <host>

S7 memory areas are declared under ``<memory_areas>`` in ``s7comm.xml`` and
backed by the databus (:doc:`../concepts/databus`). Related stop/restart
probes on Modbus and EtherNet/IP: :doc:`../usage/stop_restart`.
