# AGENTS.md — Conpot

ICS/SCADA honeypot for collecting intelligence on adversaries targeting industrial control systems. Python `>=3.14`, GPL-2.0.

Human docs: [README.md](README.md), [conpot.readthedocs.io](https://conpot.readthedocs.io/). This file is working rules for agents.

## Layout

- `conpot/core/` — databus, attack sessions, VFS, `@conpot_protocol`
- `conpot/protocols/` — one directory per protocol (+ XSD); registry in `conpot/protocols/__init__.py` (`name_mapping`)
- `conpot/templates/` — deployment profiles (`template.toml` preferred, `template.xml` still supported) plus per-protocol `*.toml` / `*.xml`
- `conpot/tests/` — pytest suite; helpers in `conpot/utils/greenlet.py`
- `conpot/cli.py` — asyncio entrypoint (`python -m conpot`)
- `tools/` — standalone helpers (`start_protocol.py`, `conpot_cloner`, `kamstrup_prober.py`)
- `docs/` — Sphinx; concepts under `docs/source/concepts/`
- `Makefile`, `pyproject.toml`, `uv.lock` — install / test / format

## Dev commands

```bash
uv sync --group dev          # make install
uv run pytest                # make test
uv run black .               # make format; make lint = black --check
uv run conpot --template default -f
```

- Python 3.14; Black **26.5.1** (pinned in `pyproject.toml`)
- Dependency changes: edit `pyproject.toml`, run `uv lock`, commit `uv.lock` with the change
- CI: pytest (`.github/workflows/python.yml`), black check, xmllint on default template XML (legacy; TOML validated via `schema` at startup)
- Deeper contributor notes: `docs/source/development/guidelines.rst`

## Code conventions

- **asyncio**, not gevent. Use `asyncio.start_server` / `create_datagram_endpoint` (or `conpot.utils.asyncio_serve`) on the supervisor loop. Do not add `monkey.patch_all()`.
- Protocol servers use `@conpot_protocol` from `conpot.core.protocol_wrapper`. Typical shape: `__init__(template, template_directory, args)`, `handle(sock, addr)`, `async def start(host, port)`, `stop()`. `start()` should set `_ready` / `_stop` `asyncio.Event`s and wait on `_stop`.
- Record attacker activity via `conpot.core.get_session(...)` then `session.add_event(...)`.
- Templates: dual-format. Prefer `templates/<name>/template.toml` (databus + metadata) and `templates/<name>/<protocol>.toml`, validated with the `schema` package (`conpot/templates/validate.py`, `conpot/protocols/schemas.py`). XML + XSD remain supported when no TOML file is present. Startup passes a **dict** for TOML protocols and a **path string** for XML; only migrate a protocol to `.toml` after its server accepts a dict (see TFTP). Keep per-protocol subdirs only for auxiliary files (e.g. `http/htdocs`). Prefer databus for shared state.
- Databus TOML mappings: plain scalars are stored as-is; use `{ value = "..." }` for eval'd expressions (like XML `type="value"`); use `{ function = "module.Class" [, params = [...]] }` for emulators.
- Style: PEP8, 4 spaces, no one-line conditionals. Run Black before claiming work done.
- Match neighboring protocol and test style when editing.

## Connection handling (TCP protocol servers)

Scanners (nmap `-A`, banner grabs, etc.) often open a socket and idle or die without a clean FIN. A `recv()` with no timeout parks the handler forever; the session never logs `CONNECTION_LOST` and looks like a one-shot alert until restart (see issue #441 / Guardian AST).

- Set `self.timeout` (typically `5`) in `__init__` and call `sock.settimeout(self.timeout)` at the start of `handle` — same pattern as S7, Modbus, IEC104, Guardian AST. Sync `handle(sock, addr)` methods run in a thread-pool executor via `serve_tcp_sync_handler`.
- Catch `socket.timeout` (and usually `socket.error`) explicitly; break out of the read loop. Do **not** swallow timeouts in a bare `except Exception` that continues the loop.
- Always finish the session: log disconnect, `session.add_event({"type": "CONNECTION_LOST"})`, and `sock.close()` (prefer `try`/`finally` so cleanup runs on timeout, peer reset, or normal close).
- Bound every read path: incomplete frames, declared lengths, and “read until delimiter” loops must not wait without a timeout (unauthenticated clients can stall a worker thread).
- Prefer `asyncio.start_server` (one Task per connection). Do not introduce a single-connection bottleneck.

## Testing

Prefer `spawn_test_server` / `teardown_test_server` from `conpot.utils.greenlet` (loads template + protocol XML, binds `127.0.0.1` on a dedicated asyncio loop thread).

Newer tests use class-scoped pytest fixtures — see `conpot/tests/test_guardian_ast.py` and `conpot/tests/test_enip_server.py`. Older tests may still use `unittest.TestCase.setUp`/`tearDown` with the same helpers.

```python
from conpot.utils.greenlet import spawn_test_server, teardown_test_server
```

Do **not** import gevent or call `monkey.patch_all()` in tests. Use stdlib `socket` / `time.sleep` / `asyncio`. Session log events live on an `asyncio.Queue`; fetch them with `asyncio.run_coroutine_threadsafe(..., handle._loop)` (see `get_log_event`).

FTP/TFTP and some protocols need VFS init (`init_test_server_by_name` / `initialize_vfs`).

## Honeypot / security constraints

- Protocol handlers speak to **untrusted** remote clients. Harden parsing and isolation; do not weaken sandboxing or privilege drop.
- Never commit real credentials or secrets. Treat `conpot/testing.cfg` sample logger settings and template SSL material under `conpot/templates/*/ssl/` as fixtures only.
- **Proxy mode** can bridge attackers to a real backend — change carefully; misconfig exposes live systems.
- Outbound sinks (hpfeeds, TAXII/STIX, syslog, JSON/SQLite) must not log or ship live secrets.
- Emulated auth in templates (FTP, IPMI, SNMP communities, etc.) is for deception — never paste real organization credentials.

## Do not duplicate here

For architecture depth (databus, templates, protocols, VFS, proxy), read `docs/source/concepts/`. Do not invent new dependency managers, linters, or async stacks without an explicit project decision.
