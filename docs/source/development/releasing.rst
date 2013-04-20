Releasing Conpot
================

Setup.py
--------

Bump the version number in the setup.py before tagging:

  version='$VERSION_NUMBER$'

Tagging
-------

Make sure to add a git tag before making a new release:

  git tag -a $VERSION_NUMBER$
  git push --tag

$VERSION_NUMBER$ should be latest pypi version +1


If you fucked up a tag, you can fix it using the following procedure:

Renaming:

  git tag new_tag old_tag

Delete the old tag:

  git tag -d old_tag

Delete the old tag on remote:

  git push origin :refs/tags/old_tag
