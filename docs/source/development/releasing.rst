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


Tagging and Pushing
-------------------

Commit all the changes you want to have in the tag.
Travis CI has been configured to deploy when it encounters a tag matching the regex 

::

    ^Release_\d{1,}\.\d{1,}\.\d{1,}



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


