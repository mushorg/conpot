# Conpot

![Test Status](https://github.com/mushorg/conpot/actions/workflows/python.yml/badge.svg)
[![Docs](https://readthedocs.org/projects/conpot/badge/?version=latest)](https://conpot.readthedocs.io/en/latest/)

## About

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and methods of adversaries targeting industrial control systems.

## Documentation

The documentation can be found [here](https://conpot.readthedocs.io/). If you are just checking out conpot, we suggest that you go for [quick install](https://conpot.readthedocs.io/en/latest/installation/quick_install.html). 

If you want to tinker around and write your own template, change ports etc., use a [host install](https://conpot.readthedocs.io/en/latest/installation/install.html). From a git checkout, dependencies are managed with [uv](https://docs.astral.sh/uv/) (`uv sync --group dev`); details are in that guide.

The FAQ is [here](https://conpot.readthedocs.io/en/latest/faq.html).

## Development / tests

Conpot requires Python >= 3.14. Install [uv](https://docs.astral.sh/uv/), then from a git checkout:

```bash
# Debian/Ubuntu: build dependencies
sudo apt-get install gcc python3-dev

# Optional: ipmitool, used by the IPMI tests (skipped if missing)
sudo apt-get install ipmitool

uv sync --group dev
uv run pytest   # or: make test (also writes junit/test-results.xml)

# Run the honeypot with the default template
uv run conpot --template default -f
```

More detail: [host install](https://conpot.readthedocs.io/en/latest/installation/install.html) and [development guidelines](https://conpot.readthedocs.io/en/latest/development/guidelines.html).
