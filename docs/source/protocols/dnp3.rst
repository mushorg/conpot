DNP3
====

The ``dnp3`` template listens for DNP3/TCP (IEEE 1815) on port **20000**.
Conpot acts as an outstation: it accepts connections, answers link-layer
frames, and serves application requests from a shared point database via
`dnp3py <https://pypi.org/project/dnp3py/>`_. Configuration lives in
``conpot/templates/dnp3/dnp3.toml``.

Start the server
----------------

DNP3-only profile (recommended for manual probes)::

    uv run conpot --template dnp3 -f

You should see DNP3 started on ``0.0.0.0:20000``. Port 20000 does not
require root.

Template configuration
----------------------

``dnp3.toml`` is validated by the ``dnp3`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 12 60

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:20000``)
   * - ``timeout``
     - ``5``
     - Idle read timeout in seconds (scanners that RST or hang)
   * - ``outstation_address``
     - ``1``
     - Link-layer destination address this outstation answers
   * - ``master_address``
     - ``0``
     - Expected master address; ``0`` means learn from the first frame
   * - ``unsolicited_enabled``
     - ``false``
     - Whether unsolicited responses are enabled in the outstation config
   * - ``binary_inputs`` / ``analog_inputs``
     - —
     - Static point table (``index`` + initial ``value``)

If neither point list is present, the server seeds binary input ``0`` and
analog input ``0`` so integrity polls still return data. Concurrent TCP
clients share one outstation and database (same as a typical RTU).

Shipped point table (``dnp3`` template)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 12 16

   * - Type
     - Index
     - Initial value
   * - Binary input
     - 0
     - ``false``
   * - Binary input
     - 1
     - ``true``
   * - Analog input
     - 0
     - ``25``
   * - Analog input
     - 1
     - ``100``

Example excerpt::

    [dnp3]
    enabled = true
    host = "0.0.0.0"
    port = 20000
    timeout = 5
    outstation_address = 1
    master_address = 0
    unsolicited_enabled = false

    [[dnp3.binary_inputs]]
    index = 0
    value = false

    [[dnp3.analog_inputs]]
    index = 0
    value = 25

Session events
--------------

Each TCP client gets an attack session. Typical ``event_type`` values:

* ``NEW_CONNECTION`` / ``CONNECTION_LOST`` — connect and cleanup
* ``LINK`` — reset link, link status, test link (request/response names in the event)
* ``REQUEST`` / ``RESPONSE`` — application function (for example ``READ``) and object groups
* ``MALFORMED`` — bytes that failed link-layer framing

Idle sockets time out after ``timeout`` seconds so banner scans do not leave
sessions hung open.

Automated tests
---------------

::

    uv run pytest conpot/tests/test_dnp3_server.py -q

The suite covers connection logging, an integrity poll against the template
points, concurrent clients on the same outstation, and peer RST cleanup.

Manual test: integrity poll
---------------------------

With the ``dnp3`` template running, in another terminal::

    uv run python

.. code-block:: python

    import asyncio
    from dnp3.datalink.builder import build_reset_link_state, build_unconfirmed_user_data
    from dnp3.datalink.parser import FrameParser
    from dnp3.master import Master
    from dnp3.master.handler import ResponseInfo, SOEHandler
    from dnp3.transport.segment import TransportSegment

    MASTER, OUTSTATION = 3, 1


    class Handler(SOEHandler):
        def __init__(self):
            self.binary_inputs = {}
            self.analog_inputs = {}

        def on_binary_input(self, values, info: ResponseInfo) -> None:
            self.binary_inputs.update({v.index: v.value for v in values})

        def on_analog_input(self, values, info: ResponseInfo) -> None:
            self.analog_inputs.update({v.index: v.value for v in values})


    async def poll(host="127.0.0.1", port=20000):
        handler = Handler()
        master = Master(handler=handler)
        reader, writer = await asyncio.open_connection(host, port)
        parser = FrameParser()
        try:
            writer.write(
                build_reset_link_state(
                    destination=OUTSTATION,
                    source=MASTER,
                    dir_from_master=True,
                ).to_bytes()
            )
            await writer.drain()
            assert list(parser.feed(await reader.read(4096)))

            segment = TransportSegment.build(
                fir=True, fin=True, seq=0,
                payload=master.build_integrity_poll().to_bytes(),
            )
            writer.write(
                build_unconfirmed_user_data(
                    destination=OUTSTATION,
                    source=MASTER,
                    dir_from_master=True,
                    user_data=segment.to_bytes(),
                ).to_bytes()
            )
            await writer.drain()
            for frame in parser.feed(await reader.read(4096)):
                if frame.user_data:
                    seg = TransportSegment.from_bytes(frame.user_data)
                    master.process_response(seg.payload)
        finally:
            writer.close()
            await writer.wait_closed()
        return handler


    h = asyncio.run(poll())
    print(h.binary_inputs)   # {0: False, 1: True}
    print(h.analog_inputs)   # {0: 25.0, 1: 100.0}

Logs should include ``NEW_CONNECTION``, ``LINK`` / ``REQUEST``, and
``CONNECTION_LOST`` when the client disconnects.
