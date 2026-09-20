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

S7 memory areas are declared under ``<memory_areas>`` in ``s7comm.xml`` and
backed by the databus (:doc:`../concepts/databus`). Related stop/restart
probes on Modbus and EtherNet/IP: :doc:`../usage/stop_restart`.
