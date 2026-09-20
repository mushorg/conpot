CPU stop and restart probes
===========================

Conpot answers common ICS scanner probes that try to stop or restart a PLC
CPU. The reply is protocol-correct and a session event is logged. The
listening process itself is **never** stopped.

.. list-table::
   :header-rows: 1
   :widths: 36 36 28

   * - Probe
     - Where it is enabled
     - Session event
   * - Modbus function 90 UMAS
     - ``plc_modbus`` (``<umas enabled="true"/>``)
     - ``UMAS_START`` / ``UMAS_STOP``
   * - S7comm job ``0x29`` / ``0x28``
     - ``default`` s7comm
     - ``PLC_STOP`` / ``PLC_START``
   * - EtherNet/IP encapsulation NOP (``0x0000``)
     - ``default`` enip
     - ``ENIP_NOP``

Manual steps and template notes live on the protocol pages:

* Modbus UMAS — :doc:`../protocols/modbus`
* S7comm CPU stop / start — :doc:`../protocols/s7comm`
* EtherNet/IP NOP (and List Identity / tags) — :doc:`../protocols/enip`

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
