# AGENTS.md — Conpot

ICS/SCADA honeypot for collecting intelligence on adversaries targeting industrial control systems. Python `>=3.14`, GPL-2.0.

Human docs: [README.md](README.md), [conpot.readthedocs.io](https://conpot.readthedocs.io/). This file is working rules for agents.

## Layout

- `conpot/core/` — databus, attack sessions, VFS, `@conpot_protocol`
- `conpot/protocols/` — one directory per protocol (+ XSD); registry in `conpot/protocols/__init__.py` (`name_mapping`)
- `conpot/templates/` — deployment profiles (`template.xml` + per-protocol XML)
- `conpot/tests/` — pytest suite; helpers in `conpot/utils/greenlet.py`
- `conpot/cli.py` — entrypoint (`monkey.patch_all()`); also `python -m conpot`
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
- CI: pytest (`.github/workflows/python.yml`), black check, xmllint on default template XML
- Deeper contributor notes: `docs/source/development/guidelines.rst`

## Code conventions

- **gevent**, not asyncio. Use `gevent.server` / greenlets; patch with `monkey.patch_all()` in entrypoints and tests.
- Protocol servers use `@conpot_protocol` from `conpot.core.protocol_wrapper`. Typical shape: `__init__(template, template_directory, args)`, `handle(sock, addr)`, `start(host, port)`, `stop()`.
- Record attacker activity via `conpot.core.get_session(...)` then `session.add_event(...)`.
- Templates: `templates/<name>/template.xml` (databus + metadata) plus `templates/<name>/<protocol>/<protocol>.xml`, validated against XSDs at startup. Prefer databus for shared state.
- Style: PEP8, 4 spaces, no one-line conditionals. Run Black before claiming work done.
- Match neighboring protocol and test style when editing.

## Testing

Prefer `spawn_test_server` / `teardown_test_server` from `conpot.utils.greenlet` (loads template + protocol XML, binds `127.0.0.1`).

Newer tests use class-scoped pytest fixtures — see `conpot/tests/test_guardian_ast.py` and `conpot/tests/test_enip_server.py`. Older tests may still use `unittest.TestCase.setUp`/`tearDown` with the same helpers.

```python
from gevent import monkey

monkey.patch_all()

from conpot.utils.greenlet import spawn_test_server, teardown_test_server
```

FTP/TFTP and some protocols need VFS init (`init_test_server_by_name` / `initialize_vfs`).

## Honeypot / security constraints

- Protocol handlers speak to **untrusted** remote clients. Harden parsing and isolation; do not weaken sandboxing or privilege drop.
- Never commit real credentials or secrets. Treat `conpot/testing.cfg` sample logger settings and template SSL material under `conpot/templates/*/ssl/` as fixtures only.
- **Proxy mode** can bridge attackers to a real backend — change carefully; misconfig exposes live systems.
- Outbound sinks (hpfeeds, TAXII/STIX, syslog, JSON/SQLite) must not log or ship live secrets.
- Emulated auth in templates (FTP, IPMI, SNMP communities, etc.) is for deception — never paste real organization credentials.

## Do not duplicate here

For architecture depth (databus, templates, protocols, VFS, proxy), read `docs/source/concepts/`. Do not invent new dependency managers, linters, or async stacks without an explicit project decision.
