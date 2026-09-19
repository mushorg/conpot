PLC emulator
============

Conpot already speaks ICS protocols, but the process data behind them is
usually static: lists filled once at startup, randomizers, or a few
callables such as uptime. The PLC emulator adds a cyclic scan over the
**databus** so a Modbus client that writes a command coil can later read a
different address area whose values changed as a result.

The attacker-facing protocol remains Conpot's existing Modbus server.

How it works
------------

Modbus blocks are named databus keys. Reads and writes slice those lists
in place (see :doc:`customization`). The scan cycle holds references to
the same lists and, every few milliseconds, runs a ``PlcEngine`` over a
shared process image:

* **coils** — writable commands from the client
* **discrete** — status bits written by the engine
* **holding** — 16-bit working registers (client-writable; the native
  engine also increments one while running)
* **analog** — 16-bit input registers written by the engine

Because the lists are shared, the next Modbus read sees the engine's
updates without extra callbacks. That matches a real PLC: a cyclic scan
samples the process image; it does not need a notification on every coil
write.

The scan runs in a gevent greenlet, started from a databus
``type="function"`` class (the same pattern as the Kamstrup usage
simulator). On shutdown the databus calls ``stop()`` on that instance.

Engines
~~~~~~~

``PlcScanCycle`` selects an engine by name:

``native``
    Hardcoded start/stop plant (`NativeLogicEngine`). This is the PoC
    backend shipped with the ``plc_modbus`` template.

``awlsim``
    Placeholder for a Siemens AWL/STL interpreter (`AwlsimEngine`). It is
    not wired yet. Selecting it fails at startup: missing ``awlsim``
    raises ``ImportError``; if the package is installed, the stub raises
    ``NotImplementedError``. Awlsim is **not** a Conpot dependency.

A later Awlsim backend is expected to map coils to S7 I (or M used as
commands), discrete inputs to Q, and holding/analog registers to MW /
PIW, and to run the interpreter in a native thread.

The ``plc_modbus`` profile
--------------------------

Use this template rather than ``default``. The default profile still
fills Modbus lists once with random values and does not start a scan.

::

    conpot --template plc_modbus -f

From a source checkout with uv: ``uv run conpot --template plc_modbus -f``.

Modbus listens on TCP port **5020**. The template uses ``mode`` serial
and a single slave with **unit ID 1**. Other unit IDs (including 255)
will not match this slave.

Native plant logic
~~~~~~~~~~~~~~~~~~

Coil ``[0]`` is start, coil ``[1]`` is stop (stop wins if both are on).
Discrete ``[0]`` is the running bit. Holding ``[0]`` increments by one
each scan while running (16-bit wrap). Analog ``[0]`` is
``holding[0] * 10`` modulo 65536, so a coil write shows up on a
**different** register type on the next read.

The scan interval in the shipped template is **50 ms**.

Address map
~~~~~~~~~~~

These numbers are the **PDU addresses** stored in ``modbus.xml``
(``starting_address``). Conpot matches requests against that value as
sent on the wire.

=============  ===================  ========================================
Client sees    Type                 Role
=============  ===================  ========================================
1              coil                 Start command
2              coil                 Stop command
10001          discrete input       Running (0 or 1)
30001          input register       Derived analog (holding × 10)
40001          holding register     Counter while running
=============  ===================  ========================================

Configuration
-------------

The profile lives under ``conpot/templates/plc_modbus/``:
``template.xml`` (databus + metadata) and ``modbus.xml`` (slave and
blocks).

Databus lists
~~~~~~~~~~~~~

Each Modbus block ``name`` must exist as a list on the databus, with the
same length as the block ``size``. Initialize with zeros (or any starting
process image) using ``type="value"``:

.. code-block:: xml

    <key name="memoryModbusSlave1BlockA">
        <value type="value">[0 for b in range(0,8)]</value>
    </key>

``PlcScanCycle`` must be constructed **after** those keys exist. Put it
last in ``key_value_mappings`` so ``databus.initialized`` is set only
when the lists are present.

Scan-cycle parameters
~~~~~~~~~~~~~~~~~~~~~

The class is registered as ``type="function"``. The optional ``param``
attribute is a Python list evaluated at startup and passed as
constructor arguments:

.. code-block:: xml

    <key name="plc_scan">
        <value type="function"
               param="[50, 'native', 'memoryModbusSlave1BlockA', 'memoryModbusSlave1BlockB', 'memoryModbusSlave1BlockD', 'memoryModbusSlave1BlockC']">conpot.emulators.plc.scan_cycle.PlcScanCycle</value>
    </key>

In order:

1. ``scan_ms`` — period of one scan (milliseconds; minimum 1)
2. ``engine_name`` — ``native`` or ``awlsim``
3. ``coils_key`` — databus key for coils
4. ``discrete_key`` — databus key for discrete inputs
5. ``holding_key`` — databus key for holding registers
6. ``analog_key`` — databus key for analog / input registers

The constructor has the same defaults as the ``plc_modbus`` template, so
an empty ``param`` still works if your keys keep those names.

Modbus blocks
~~~~~~~~~~~~~

Point each ``<block name="...">`` at the same databus key. Example coil
block:

.. code-block:: xml

    <block name="memoryModbusSlave1BlockA">
        <type>COILS</type>
        <starting_address>1</starting_address>
        <size>8</size>
        <content>memoryModbusSlave1BlockA</content>
    </block>

``<content>`` is documentation only. Keep ``size`` equal to the list
length. ``delay`` in the shipped template is ``0`` so tests and interactive
clients are not slowed by an extra turnaround wait.

Changing the plant
~~~~~~~~~~~~~~~~~~

To use a different start/stop layout, either:

* edit ``NativeLogicEngine.scan`` in
  ``conpot/emulators/plc/native.py``, or
* add another ``PlcEngine`` and select it from ``_make_engine`` /
  ``engine_name``.

Do not upload AWL from the network; programs are template assets.

Testing
-------

Automated tests
~~~~~~~~~~~~~~~

::

    uv run pytest conpot/tests/test_plc_modbus.py -q

The suite writes the start coil, waits at least one scan, then asserts
that the running bit is set and the holding register increases; it then
writes stop and asserts that running clears and the counter freezes.
Existing ``test_modbus_server.py`` still targets the ``default``
template.

``tools/start_protocol.py modbus`` is not useful here: that helper loads
``default``, which has no scan cycle.

Manual test: start Conpot
~~~~~~~~~~~~~~~~~~~~~~~~~

::

    uv run conpot --template plc_modbus -f

You should see Modbus started on ``0.0.0.0:5020``. Port 5020 does not
require root. Use **slave / unit ID 1**.

Manual test: Python (pymodbus)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In another terminal, outside the Conpot process:

::

    uv run python

.. code-block:: python

    import time
    from pymodbus.client import ModbusTcpClient

    m = ModbusTcpClient("127.0.0.1", port=5020, timeout=2)
    m.connect()
    slave = 1

    def snap():
        coils = m.read_coils(1, count=2, device_id=slave)
        run = m.read_discrete_inputs(10001, count=1, device_id=slave)
        hold = m.read_holding_registers(40001, count=1, device_id=slave)
        analog = m.read_input_registers(30001, count=1, device_id=slave)
        print(
            "coils", coils.bits,
            "running", run.bits,
            "holding", hold.registers,
            "analog", analog.registers,
        )

    snap()
    m.write_coils(1, [True, False], device_id=slave)
    time.sleep(0.3)
    snap()
    time.sleep(0.3)
    snap()
    m.write_coils(1, [False, True], device_id=slave)
    time.sleep(0.2)
    snap()
    m.close()

After start, discrete 10001 should be ``1`` and holding 40001 should
increase between snaps. Analog 30001 should be about ``holding * 10``.
After stop, running is ``0`` and holding stays put.

Manual test: mbpoll
~~~~~~~~~~~~~~~~~~~

Conpot matches the **PDU address** as sent on the wire. Many clients,
including ``mbpoll``, default to 1-based numbering and subtract one
before sending, so ``-r 1`` would write PDU address 0, which is outside
the coil block (starts at 1) and returns **illegal data address**
(exception 2).

Pass ``-0`` so mbpoll sends the reference unchanged. ``-1`` polls once
instead of looping:

::

    mbpoll -m tcp -a 1 -t 0 -0 -r 1 127.0.0.1 -p 5020 1 0
    mbpoll -m tcp -a 1 -t 1 -0 -r 10001 -c 1 -1 127.0.0.1 -p 5020
    mbpoll -m tcp -a 1 -t 4 -0 -r 40001 -c 1 -1 127.0.0.1 -p 5020
    mbpoll -m tcp -a 1 -t 3 -0 -r 30001 -c 1 -1 127.0.0.1 -p 5020
    mbpoll -m tcp -a 1 -t 0 -0 -r 1 127.0.0.1 -p 5020 0 1

``-t 0`` coils, ``-t 1`` discrete inputs, ``-t 3`` input registers,
``-t 4`` holding registers.

Logs
~~~~

Each client action should log a new Modbus session and function codes
(1 / 2 / 3 / 4 / 15). If values never change, the usual causes are the
``default`` template, the wrong unit ID, or an addressing convention that
misses the block (as with mbpoll without ``-0``).
