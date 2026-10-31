======================
Development Guidelines
======================

Developers Guide
================

Style and formatting
--------------------
* Follow `PEP 8 <https://peps.python.org/pep-0008/>`_.
* Indent with 4 spaces (no tabs).
* No one-line conditionals.
* Code is formatted with `Black <https://black.readthedocs.io/>`_. The version is pinned in
  ``pyproject.toml``; run ``uv run black .`` (``make format``) before committing. CI runs
  ``uv run black --check .`` (``make lint``) and fails on unformatted code.
* Match the style of neighboring protocols and tests when editing existing code.

Code conventions
----------------
* Conpot runs on **asyncio**. Do not add gevent or ``monkey.patch_all()``.
* Protocol servers live in ``conpot/protocols/<name>/``, use the ``@conpot_protocol`` decorator
  and are registered in ``conpot/protocols/__init__.py``.
* Protocol handlers talk to untrusted clients: set socket timeouts, bound every read, and always
  log ``CONNECTION_LOST`` and close the socket (use ``try``/``finally``).
* Never commit real credentials. Emulated credentials in templates are for deception only.

``AGENTS.md`` in the repository root keeps a more detailed, up-to-date list of these rules. For
architecture background see :doc:`../concepts/protocols`, :doc:`../concepts/templates` and
:doc:`../concepts/databus`.

Python environment (uv)
-----------------------

Dependencies are declared in ``pyproject.toml`` and locked in ``uv.lock``. Install `uv <https://docs.astral.sh/uv/>`_, then from the repository root:

::

  uv sync --group dev

That creates ``.venv`` and installs the project plus development tools (pytest, etc.). Typical commands:

::

  uv run pytest
  uv run conpot --template default -f
  uv run black .

The root ``Makefile`` exposes ``make install``, ``make test``, and ``make format`` around the same uv commands.

When you add or change a dependency, update ``pyproject.toml``, run ``uv lock``, and commit ``uv.lock`` together with your change.

Read the Docs builds use the root ``.readthedocs.yaml``: the ``install`` job runs ``uv sync --frozen --link-mode=copy`` into ``$READTHEDOCS_VIRTUALENV_PATH`` so published docs match the lockfile. Commit ``uv.lock`` whenever dependencies change or doc builds on Read the Docs will fail.

Running the test suite
----------------------

1. Install system packages for your distribution. On Debian/Ubuntu, besides the build
   dependencies listed in :doc:`../installation/install`, install ``ipmitool`` (required
   by the IPMI tests; not needed to run Conpot itself)::

     sudo apt-get install ipmitool

2. Sync the project and the ``dev`` dependency group, then run pytest::

     uv sync --group dev
     uv run pytest

   Equivalent: ``make install`` then ``make test``.

CI (``.github/workflows/python.yml``) installs ``gcc`` and ``ipmitool``, runs
``uv sync --frozen --group dev``, then ``uv run pytest``.

Copyright
---------
* If you are adding a file/code which is produced only by you, feel free to add the license information and a notice who holds the copyrights.

Use of AI coding agents
-----------------------

Contributions written with the help of AI coding agents or assistants (for example Claude Code,
GitHub Copilot, Cursor or Codex) are welcome, under these conditions:

* **Disclose it.** State in the pull request description that an AI agent was used, which tool,
  and roughly for what (e.g. "tests generated with Claude Code, protocol parser written by hand").
  Commits substantially authored by an agent should carry a ``Co-Authored-By:`` trailer naming the
  tool, as most agents add by default. Do not strip it.
* **You are the author.** You must understand, review and be able to explain every line you
  submit. "The agent wrote it" is not an answer in code review.
* **Verify it.** Run ``make test`` and ``make lint`` locally. Do not submit code or tests you have
  not run, and do not let an agent weaken or delete tests to make them pass.
* **Mind the threat model.** Conpot parses traffic from hostile clients. Pay particular attention
  to agent-generated parsing code, timeouts, proxy mode and anything touching privilege drop or
  sandboxing.
* **No secrets.** Never paste credentials, tokens or private data into an agent session.
* **Licensing.** You are responsible for making sure agent output does not reproduce code under
  an incompatible license. Conpot is GPL-2.0.

Agents should read ``AGENTS.md`` in the repository root, which contains the project's working
rules for automated contributors. Keep it in sync when conventions in this document change.

Recommended git workflow
------------------------

For contributors
~~~~~~~~~~~~~~~~

0, You can do this step when you are on main, or feature_branch, anytime there are new commits in original project.

Just one-time add of remote:

::

  git remote add mushorg https://github.com/mushorg/conpot.git

And rebase:

::

  git fetch mushorg
  git rebase mushorg/main feature_branch

This way, your feature_branch or main will be up-to-date.

1, For every feature, create new branch:

::

  git checkout -b feature_branch

2, State what you do in commit message.

When you create pull request and get review, it is recommended to edit your original commits.

3a, If you want to change the last commit:

::

  (make some changes in files)
  git add file1 file2
  git commit --amend

3b, If you want to change any of your previous commits:

::

  git rebase -i HEAD~3  (can be HEAD~4, depends which commit you want to change, or you can type hash of previous commit)

change "pick" to "e":

::

  e e88a2f1 commit 1
  pick bfd57e4 commit2

and save.

::

  (make some changes in files)
  git add file1 file2
  git rebase --continue

Warning:
Do not use 'git commit' in rebase if you don't know what you are doing.

4, Look at your changes, and git force push to your branch:

::

  git push --force-with-lease origin feature_branch

5, Comment in pull request to let us know about your new code.

For maintainers
~~~~~~~~~~~~~~~

To avoid additional Merge commits, use cherry-pick:

::

  git checkout main
  git remote add user https://github.com/user/conpot.git
  git fetch user
  (look at 'git log user/feature_branch')
  git cherry-pick commit_hash
  git push origin main
  git remote rm user

Comment on pull request that you added it to main, and close pull request.

This approach is useful for majority of pull requests (1-3 commits).

If you expect conflicts (a lot of commits in feature branch with a lot of changes) you can use GitHub Merge button.

Revert will be easier too.

Conflicts should not happen, if feature branch is rebased on current main.
