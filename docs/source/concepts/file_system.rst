ConpotFS
========

ConpotFS designed to have "safe to use" `os.*` wrappers that could be used by protocols. We cannot allow `chmod()` like commands that may allow attackers to make arbitrary system calls.

At the same time - protocols such as FTP need `chmod()` like methods. Same goes for `stat()` etc. For this reason, we needed a file system that can operate on a layer above the actual file system and still provide the flexibility/robustness.

The Conpot's file system solves this problem by proxying the actual files kept at a controlled location.

::


        +---------------+                      +----------------------+
        |               |                      |                      |
        |               | <----------------+   |  Actual FileSystem   |
        |  Conpot VFS   |       Proxy          |         at           |
        |               | +---------------->   |  '/tmp/__conpot__*/' |
        |               |                      |                      |
        +---------------+                      +----------------------+

Consequently, we would keep a cache (a dictionary where we would store all file related data - (information regarding access, permissions, owners, stat etc.). Note that no matter what, we won't change the actual permissions of the file system.

For the sake of demo, consider the following:

This is what a typical `ls -la` for a user `1337honey` looks like:

::

        total 8
        drwxrwxr-x 2 1337honey 1337honey 4096 Jul  9 01:20 .
        drwxrwxr-x 4 1337honey 1337honey 4096 Jul  9 01:17 ..
        -rw-rw-r-- 1 1337honey 1337honey    0 Jul  9 01:20 hacked.png

Notice the permissions and the user/group.

.. code-block:: python

    >>> import conpot.core as conpot_core
    >>> conpot_core.initialize_vfs('.', data_fs_path='../data_fs')
    >>> vfs = conpot_core.get_vfs()
    >>> vfs.listdir('.')
    ['hacked.png']
    >>> [print(i) for i in vfs.format_list('', vfs.listdir('.'))]
    rwxrwxrwx   1 root     root            0 Jul 08 19:53 hacked.png

As you can see, the permissions have changed and so have the user/groups(By default the `uid:gid` is `0:0` and permissions is `777` - this is configurable).
This is not all. Check this out!

.. code-block:: python

    >>> vfs.register_user('attacker', 2000)
    >>> vfs.create_group('attacker', 3000)
    >>> vfs.chown('/', uid=2000, gid=3000, recursive=True)
    >>> vfs.chmod('/', 0o755, recursive=True)
    >>> [print(i) for i in vfs.format_list('', vfs.listdir('.'))]
    rwxr-xr-x   1 attacker   attacker          0 Jul 08 19:53 hacked.png

There is no change with the uid:gid:perms of the actual `'hacked.png'` file though.

Another big advantage of this approach is : VFS is independent of the physical storage media it is located in. We are currently keeping the contents in '/tmp'. But in future if we want to replace this with somewhat better storage media(or location), we can simply detach the VFS - replace it with new storage media URL and it'll fit right in.

