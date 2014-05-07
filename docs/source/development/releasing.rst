Releasing Conpot
================

Update Readme
-------------

Update the README with the sample output and the new version.


Check Tests
-----------

Make sure all tests are passing:

::

  nosetests


Check Usage
-----------

Run the server to see if he loads properly.

::

    python conpot


Setup.py
--------

Bump the version number in conpot/__init__.py before tagging:

::

    version='$VERSION_NUMBER$'


Tagging and Pushing
-------------------

Commit all the changes you want to have in the tag.
Make sure to add a git tag before making a new release:

::

    git tag -a $VERSION_NUMBER$
    git push --tag

$VERSION_NUMBER$ should be latest pypi version +1


Mess ups
~~~~~~~~

If you fucked up a tag, you can fix it using the following procedure:

Renaming:

::

    git tag new_tag old_tag

Delete the old tag:

::

    git tag -d old_tag

Delete the old tag on remote:

::

    git push origin :refs/tags/old_tag


Release
-------

Build the package:
~~~~~~~~~~~~~~~~~~

::

    python setup.py sdist

Get the PKG-INFO from the .tgz in dist/package.tgz
Create new release on PyPI and add PKG-INFO to new release. Upload the .tgz

Update the documentation:
~~~~~~~~~~~~~~~~~~~~~~~~~

::

    ./docs/update-site.sh


