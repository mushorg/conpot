================
Development Guidelines
================

Developers Guide
================

Indentation
-----------
* We are using 4 tab-spaces
* No one line conditionals

Style
-----
* We obey to the `PEP8 <http://www.python.org/dev/peps/pep-0008/>`_

Python environment (uv)
-----------------------

Dependencies are declared in ``pyproject.toml`` and locked in ``uv.lock``. Install `uv <https://docs.astral.sh/uv/>`_, then from the repository root:

::

  uv sync --group dev

That creates ``.venv`` and installs the project plus development tools (pytest, pytest-cov, etc.). Typical commands:

::

  uv run pytest
  uv run conpot --template default -f
  uv run black .

The root ``Makefile`` exposes ``make install``, ``make test``, and ``make format`` around the same uv commands.

When you add or change a dependency, update ``pyproject.toml``, run ``uv lock``, and commit ``uv.lock`` together with your change.

Read the Docs builds use the root ``.readthedocs.yaml``: the ``install`` job runs ``uv sync --frozen --link-mode=copy`` into ``$READTHEDOCS_VIRTUALENV_PATH`` so published docs match the lockfile. Commit ``uv.lock`` whenever dependencies change or doc builds on Read the Docs will fail.

Copyright
---------
* If you are adding a file/code which is produced only by you, feel free to add the license information and a notice who holds the copyrights.

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

  git push -f feature_branch

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

This approach is usefull for majority of pull requests (1-3 commits).

If you expect conflicts (a lot of commits in feature branch with a lot of changes) you can use GitHub Merge button.

Revert will be easier too.

Conflicts should not happen, if feature branch is rebased on current main.
