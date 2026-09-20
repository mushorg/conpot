Databus
=======

The databus is Conpot's shared in-memory key/value store. Protocol handlers do not
keep their own copies of plant identity strings, register maps, or sensor readings.
They read and write named keys on the databus so that the same logical value can
appear consistently across Modbus, SNMP, S7, HTTP, and other enabled protocols.

Implementation: ``conpot.core.databus.Databus``. Access the process-wide instance
with ``conpot.core.get_databus()``.

Why it exists
-------------

Industrial devices expose the same underlying state through several protocols.
A honeypot profile that claims to be a Siemens PLC should return matching vendor
strings, memory contents, and uptime whether the attacker probes SNMP or Modbus.
The databus is the single place those values live for a running template.

Lifecycle
---------

1. Conpot creates one ``Databus`` instance at import time (see ``conpot.core``).
2. At startup, ``cli`` (and the test helpers) call ``get_databus().initialize(...)``
   with either a parsed ``template.toml`` dict or a legacy ``template.xml`` path.
3. ``initialize`` loads every key from ``core.databus.key_value_mappings`` (TOML) or
   ``//core/databus/key_value_mappings/*`` (XML), then sets ``databus.initialized``
   (a ``threading.Event``).
4. Protocol servers start after that and resolve template references to databus keys.
5. ``reset()`` clears keys and observers; any stored object with a ``stop()`` method
   is stopped first (used by long-running emulators).

Emulators that start their own background threads should wait until the bus is ready::

    databus = conpot.core.get_databus()
    databus.initialized.wait()

Template configuration
----------------------

**TOML (preferred).** Keys are declared in ``template.toml``:

.. code-block:: toml

    [core.databus.key_value_mappings]
    SystemDescription = "Siemens, SIMATIC, S7-200"
    Uptime = { function = "conpot.emulators.misc.uptime.Uptime" }
    memoryModbusSlave0BlockA = { value = "[random.randint(0,1) for b in range(0,128)]" }

* Plain scalars are stored as-is.
* ``{ value = "..." }`` — the string is passed to ``eval()`` (same trust model as XML
  ``type="value"``). ``random`` is available in that evaluation context.
* ``{ function = "module.Class" [, params = [...]] }`` — import path of a class;
  Conpot stores an instance (optional ``params`` list for the constructor).

**XML (legacy).** Keys are declared in the profile's ``template.xml`` under
``<core><databus>``:

.. code-block:: xml

    <databus>
        <key_value_mappings>
            <key name="SystemDescription">
                <value type="value">"Siemens, SIMATIC, S7-200"</value>
            </key>
            <key name="Uptime">
                <value type="function">conpot.emulators.misc.uptime.Uptime</value>
            </key>
            <key name="memoryModbusSlave0BlockA">
                <value type="value">[random.randint(0,1) for b in range(0,128)]</value>
            </key>
        </key_value_mappings>
    </databus>

``type`` must be one of:

* ``value`` — the text of ``<value>`` is passed to ``eval()`` and stored as-is.
  Strings need quotes; lists and expressions are allowed. ``random`` is available
  in that evaluation context (imported in ``databus.py`` for template use).
* ``function`` — the text is an import path ``module.ClassName``. Conpot imports
  the class and stores an instance. Optional constructor arguments can be supplied
  with a ``param`` attribute on ``<value>`` (a Python list literal evaluated at load
  time).

Protocol config files (for example ``snmp.xml`` / ``tftp.toml``, ``modbus.xml``)
usually store a **databus key name**, not the payload itself. Missing keys raise
``AssertionError`` when a handler calls ``get_value``.

S7 memory areas are declared under ``<memory_areas>`` in ``s7comm.xml``. Each
``<area>`` maps an S7 address space (``DB``, ``M``, ``I``, or ``Q``) to a databus
key. Prefer ``bytearray`` values for those keys so Read/Write VAR can mutate the
process image in place (Modbus blocks typically use lists of ints instead).

See :doc:`../protocols/snmp` and :doc:`../protocols/modbus` for examples that
wire symbols and memory blocks to databus keys.

Python API
----------

.. code-block:: python

    import conpot.core as conpot_core

    databus = conpot_core.get_databus()

    databus.get_value("SystemDescription")
    databus.set_value("SystemDescription", "other vendor string")
    databus.observe_value("reboot_signal", callback)

``get_value(key)``
    Returns the current value for ``key``. Resolution order:

    1. If the stored object has a ``get_value`` method, call it and return the result
       (typical for emulator classes such as ``Uptime``).
    2. Else if the object is callable, call it with no arguments.
    3. Else return the stored object directly (strings, lists, ints, …).

``set_value(key, value)``
    Stores ``value`` under ``key`` and notifies observers registered for that key
    (on the running asyncio loop via ``create_task``, or a daemon thread if no
    loop is running).

``observe_value(key, callback)``
    Registers ``callback`` to run when ``key`` is written. The callback must be
    callable and take at least one argument (the key name). Used for cross-protocol
    side effects — for example Kamstrup observes ``reboot_signal`` to simulate a
    device reboot without restarting the process.

``initialize(config_file)`` / ``reset()``
    Load or tear down the key set. Prefer letting Conpot's startup path call these;
    tests use the same helpers via ``conpot.utils.greenlet`` (asyncio loop-thread
    harness; name kept for compatibility).

Writing an emulator
-------------------

Dynamic values (uptime counters, noisy registers, simulated meters) belong in a
small class under ``conpot/emulators/`` and are registered with
``type="function"``.

Minimal pattern (see ``conpot.emulators.misc.uptime.Uptime``)::

    class Uptime:
        def __init__(self, started=-1):
            ...

        def get_value(self):
            return calendar.timegm(time.gmtime()) - self.started

If the emulator owns a background thread, implement ``stop()`` so ``reset()``
can shut it down cleanly.

How protocols use the databus
-----------------------------

* **SNMP** — each MIB symbol's ``<value>`` is a databus key; ``DatabusMediator``
  reads and writes through the bus.
* **Modbus** — coil/register blocks reference databus keys that hold lists; the
  ``ModbusBlockDatabusMediator`` indexes those lists.
* **S7** — SSL / identity fields resolve through databus keys defined in the
  S7 template.
* **HTTP** — template tags can pull live values with
  ``source="databus"`` and a ``key`` attribute.
* **IPMI / Kamstrup / others** — device name, MAC, registers, and control signals
  follow the same pattern.

New protocol handlers should take the same approach: keep deception state on the
databus, not in module globals, so operators can reshape the whole profile from
``template.xml``.

Notes for contributors
----------------------

* ``get_value`` asserts that the key exists. Fail fast in templates rather than
  returning silent defaults.
* ``type="value"`` uses ``eval``. Keep template expressions simple and treat
  profile XML as trusted configuration written by the operator.
* Observers run asynchronously (asyncio task or thread). Avoid calling back into
  the databus from ``get_value`` implementations in a way that re-enters the same
  key while observers are firing.
* Prefer shared databus keys over duplicating strings in every protocol XML file.
