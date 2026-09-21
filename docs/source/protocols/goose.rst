GOOSE (R-GOOSE)
===============

The ``goose`` template listens for **IEC 61850-90-5 Routed-GOOSE (R-GOOSE)**
over UDP on port **10200**. Conpot emulates an IED that both **subscribes**
(decode and log inbound unsecured R-GOOSE datagrams) and **publishes**
template-driven unsecured R-GOOSE keepalives.

This is **not** native Layer-2 GOOSE (EtherType ``0x88B8``). L2 GOOSE remains
out of scope for this handler; see GitHub issue `#208`.

Start the server
----------------

R-GOOSE-only profile::

    uv run conpot --template goose -f

You should see GooseServer listening on ``0.0.0.0:10200``. Port 10200 does not
require root (IEC literature often cites UDP/102 for 90-5; Conpot uses a
non-privileged default).

Template configuration
----------------------

``goose.toml`` is validated by the ``goose`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 14 58

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:10200``)
   * - ``appid``
     - ``1``
     - 16-bit APPID in published / expected frames
   * - ``gocb_ref`` / ``dat_set`` / ``go_id``
     - sample IED paths
     - GOOSE control-block identity strings
   * - ``conf_rev`` / ``time_allowed_to_live``
     - ``1`` / ``10000``
     - Configuration revision and TAL (ms)
   * - ``publish_interval_ms``
     - ``200``
     - Retransmit period for the publisher task
   * - ``publish_dest`` / ``publish_dest_port``
     - ``127.0.0.1`` / ``10201``
     - UDP destination for published frames (``0`` = bound listen port)
   * - ``multicast_group``
     - unset
     - Optional ``IP_ADD_MEMBERSHIP`` join for RX
   * - ``all_data``
     - boolean + integer sample
     - Dataset members (``boolean`` or ``integer`` entries only)

Security is the **unsecured** 90-5 profile only (no KDC / HMAC). Do not paste
real plant ``gocbRef`` strings into templates.

Probe with the standard library
-------------------------------

Send a crafted R-GOOSE datagram (build helpers live under
``conpot.protocols.goose``)::

    import socket
    from conpot.protocols.goose.goose_apdu import encode_goose_apdu
    from conpot.protocols.goose.session90_5 import pack_rgoose

    apdu = encode_goose_apdu(
        gocb_ref="IED1/LLN0$GO$gcb01",
        time_allowed_to_live=10000,
        dat_set="IED1/LLN0$dataset1",
        go_id="GOOSE1",
        st_num=1,
        sq_num=0,
        conf_rev=1,
        all_data=[False, 42],
    )
    packet = pack_rgoose(apdu, appid=1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(packet, ("127.0.0.1", 10200))
    sock.close()

Capture published frames by binding UDP to ``publish_dest_port`` (shipped
``10201``) or by pointing ``publish_dest`` / ``publish_dest_port`` at a
local listener.
