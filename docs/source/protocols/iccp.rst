ICCP / TASE.2
=============

The ``iccp`` template emulates a **called** Inter-Control Center Communications
Protocol endpoint (IEC 60870-6 TASE.2) over ISO-on-TCP. Conpot accepts inbound
TCP associations on port **102**, completes a minimal MMS Initiate, and answers
Identify / GetNameList / Read against a small template VCC domain.

This is a honeypot subset for scanners and peer probes — not a full bilateral
TASE.2 stack. Block 2 RBE, Blocks 4/5, TLS (3782), and proxying to a live ICCP
peer are out of scope; see GitHub issue `#70`.

Start the server
----------------

ICCP-only profile::

    uv run conpot --template iccp -f

You should see ICCPServer listening on ``0.0.0.0:102``. Do not enable ``iccp``
alongside ``s7comm`` on the same host address if both claim port 102.

Template configuration
----------------------

``iccp.toml`` is validated by the ``iccp`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 14 58

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:102``)
   * - ``timeout``
     - ``5``
     - Socket read timeout (seconds); ends idle scanner sessions
   * - ``vendor`` / ``model`` / ``revision``
     - Conpot / ICCP-TASE2 / 1.0
     - MMS Identify-Response strings
   * - ``domain``
     - ``VCC``
     - MMS domain name advertised for GetNameList
   * - ``[[iccp.points]]``
     - sample points
     - Named variables (``name``, ``type``, ``value``)

Point ``type`` may be ``boolean``, ``integer``, or ``float``.

How to probe
------------

Use a stdlib TCP client or any ISO-on-TCP MMS Identify probe against the listen
port (for example ``nmap -p 102 --script iec61850-mms 127.0.0.1``). Association is
COTP Connection Request → MMS Initiate → MMS Identify. Session events are
logged as ``NEW_CONNECTION``, ``REQUEST``, and ``CONNECTION_LOST``.

Scope
-----

Implemented:

* ISO-on-TCP (TPKT + COTP CR/CC/DT)
* MMS Initiate / Conclude
* MMS Identify, GetNameList, Read for template domain points

Deferred:

* Bilateral tables and access control
* Data Set Transfer Sets / report-by-exception (Block 2)
* Information messages and device control (Blocks 4/5)
* IEC 62351 / TLS on port 3782
