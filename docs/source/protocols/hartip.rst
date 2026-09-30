HART-IP
=======

The ``hartip`` template listens for **HART-IP** (Highway Addressable Remote
Transducer over IP) on TCP port **5094**. Conpot emulates a HART-IP gateway /
field device that answers session setup and the identity commands commonly used
by scanners (``nmap`` ``hartip-info`` and the community ``hartip.nse`` probe).

UDP transport, HART-IP v2 (TLS), burst/publish, and the full universal command
set are out of scope for this handler; see GitHub issue `#219`.

Start the server
----------------

HART-IP-only profile::

    uv run conpot --template hartip -f

You should see HartipServer listening on ``0.0.0.0:5094``.

Template configuration
----------------------

``hartip.toml`` is validated by the ``hartip`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 14 58

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:5094``)
   * - ``timeout``
     - ``5``
     - Idle recv timeout in seconds (issue `#441`)
   * - ``manufacturer_id``
     - ``176``
     - 16-bit manufacturer code in Command 0
   * - ``private_label_distributor``
     - same as manufacturer
     - Private label code in Command 0
   * - ``expanded_device_type``
     - ``45075`` (``0xB013``)
     - Expanded device type in Command 0 (``hartip-info`` maps this to ``GW PL ETH/UNI-BUS``)
   * - ``device_id``
     - ``000001``
     - 3-byte device ID as hex
   * - ``long_tag``
     - ``Conpot HART-IP Gateway``
     - 32-octet Command 20 long tag
   * - ``hart_revision``
     - ``7``
     - HART protocol major revision

Do not paste real organization device IDs or tags into templates.

Supported messages
------------------

* Session Initiate / Close / Keep-Alive
* Pass-Through Command **0** (Read Unique Identifier)
* Pass-Through Command **20** (Read Long Tag)
* Pass-Through Command **84** (Read Sub-Device Identity Summary) returns HART
  response code ``2`` (no sub-device)

Probe with nmap
---------------

Neither script ships with every nmap build. Fetch them into a directory nmap can
read (snap-confined nmap often cannot open ``/tmp``; ``$HOME`` works)::

    mkdir -p ~/nse
    curl -sSL -o ~/nse/hartip-info.nse \
      https://raw.githubusercontent.com/nmap/nmap/master/scripts/hartip-info.nse
    curl -sSL -o ~/nse/hartip.nse \
      https://api.bitbucket.org/2.0/repositories/dark_k3y/hartnse/src/master/hartip.nse

With Conpot listening (``uv run conpot --template hartip -f``), run a connect
scan (``-sT``) so root is not required::

    nmap -sT -Pn -p 5094 --script ~/nse/hartip-info.nse 127.0.0.1
    nmap -sT -Pn -p 5094 --script ~/nse/hartip.nse 127.0.0.1

``hartip.nse`` should report ``detected HART RTU gateway``. Upstream
``hartip-info.nse`` parses Command 0 identity; with the shipped template it
shows manufacturer **Phoenix Contact** and expanded device type
**GW PL ETH/UNI-BUS**.

Command 20 (long tag) from ``hartip-info.nse`` may fail: that script hardcodes
a checksum valid only for one sample device address. Conpot rejects the bad
frame (logged as a checksum mismatch) the same way a real device would; the
script still returns Command 0 fields.

Probe with the standard library
-------------------------------

Send a Session Initiate (same bytes as the community NSE detection probe)::

    import socket

    sess = bytes.fromhex("010000000001000D0100004E20")
    sock = socket.create_connection(("127.0.0.1", 5094), timeout=2)
    sock.sendall(sess)
    data = sock.recv(64)
    sock.close()
    # Response: version=1, message_type=1 (Response), transaction_id=1
    assert data[0] == 1 and data[1] == 1 and data[4:6] == b"\x00\x01"
