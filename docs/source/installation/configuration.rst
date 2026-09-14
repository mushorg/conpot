Basic Configuration
===================

Basic configuration options are provided in the default configuration file:
::

    [common]
    sensorid = default

    [sqlite]
    enabled = False

    [json]
    enabled = False
    filename = /var/log/conpot.json

    [syslog]
    enabled = False
    device = /dev/log
    host = localhost
    port = 514
    facility = local0
    socket = dev        ; udp (sends to host:port), dev (sends to device)

    [hpfriends]
    enabled = False
    host = hpfriends.honeycloud.net
    port = 20000
    ident = 3Ykf9Znv
    secret = 4nFRhpm44QkG9cvD
    channels = ["conpot.events", ]

    [taxii]
    enabled = False
    host = taxiitest.mitre.org
    port = 80
    inbox_path = /services/inbox/default/
    use_https = False

    [fetch_public_ip]
    enabled = True
    urls = ["http://whatismyip.akamai.com/", "http://wgetip.com/"]

Please note that by enabling hpfriends your conpot installation will automatically transmit attack data to The Honeynet
Project. The fetch_public_ip option enables fetching the honeypot public ip address from a external resource.

Attack event schema
-------------------

Protocol sessions emit structured attack events (schema version 1) to the logging sinks.
Each event is a JSON object with these fields:

* ``schema_version`` — integer schema version (currently ``1``)
* ``sensorid`` — value from ``[common] sensorid``
* ``session_id`` — UUID string for the connection session
* ``protocol`` — protocol name (for example ``modbus``, ``http``)
* ``session_time`` / ``event_time`` — ISO-8601 UTC timestamps for session start and this event
* ``src_ip``, ``src_port``, ``dst_ip``, ``dst_port`` — connection endpoints
* ``public_ip`` — honeypot public IP when ``fetch_public_ip`` is enabled
* ``event_type`` — high-level event label when provided (for example ``NEW_CONNECTION``)
* ``request``, ``response``, ``error`` — lifted protocol payload fields when present
* ``data`` — remaining protocol-specific fields

Enabled sinks all receive the same event object:

* **json** — one NDJSON line per event
* **sqlite** — relational columns plus full ``event_json``
* **syslog** — one JSON line on the ``conpot.attack`` logger
* **hpfriends** / **taxii** — same structured payload (HPFriends JSON shape changed with schema v1)
