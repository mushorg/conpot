Kamstrup meter (KMP)
====================

The ``kamstrup_382`` template exposes the **Kamstrup Meter Protocol (KMP)** on
TCP port **1025** via ``kamstrup_meter``. Conpot emulates a Kamstrup 382-style
meter that answers register reads and the meter login (password) command used
by management tools such as Metertool.

The companion ``kamstrup_management`` handler on port **50100** is a separate
telnet-style management menu and is not covered here.

Start the server
----------------

Kamstrup profile::

    uv run conpot --template kamstrup_382 -f

You should see KamstrupServer listening on ``0.0.0.0:1025``.

Template configuration
----------------------

``kamstrup_meter.toml`` is validated by the ``kamstrup_meter`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 14 58

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:1025``)
   * - ``communication_address``
     - ``63`` (``0x3F``)
     - KMP destination address expected in requests
   * - ``login_pin``
     - ``12345``
     - Deception meter password for CID ``0x92`` (uint16)
   * - ``registers``
     - —
     - Register table (name, length, units, mystery byte, databus key)

``login_pin`` is a honeypot deception value (Metertool's documented default is
``12345``). Do not paste a real organization meter password into templates.

Supported messages
------------------

* **Get registers** (CID ``0x10``) — return configured register values from the
  databus
* **Login** (CID ``0x92``) — accept a two-byte PIN; reply with status ``0x00``
  (accepted) or ``0x01`` (denied). Exact meter status codes are not publicly
  documented; this subset is enough for scanners and tools that attempt a
  password before programming commands.

GetType (CID ``0x01``) and session-gated command enforcement after login are
not implemented yet (see GitHub issue `#177` for the login work).

Probe with the standard library
-------------------------------

Build a login frame (address ``0x3F``, PIN ``12345``) and read the status byte::

    import socket
    from crc16.crc16pure import crc16xmodem

    pin = 12345
    body = bytes([0x3F, 0x92, (pin >> 8) & 0xFF, pin & 0xFF])
    crc = crc16xmodem(body)
    frame = bytes([0x80]) + body + bytes([crc >> 8, crc & 0xFF, 0x0D])

    sock = socket.create_connection(("127.0.0.1", 1025), timeout=2)
    sock.sendall(frame)
    data = sock.recv(64)
    sock.close()
    # Response magic 0x40, address 0x3F, CID 0x92, status 0x00 (accepted)
    assert data[0] == 0x40 and data[1] == 0x3F and data[2] == 0x92 and data[3] == 0
