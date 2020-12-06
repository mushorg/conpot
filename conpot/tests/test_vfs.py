# Copyright (C) 2018  Abhinav Saxena <xandfury@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
Test core features for Conpot's virtual file system
"""
import conpot.core as conpot_core
from conpot.core.filesystem import SubAbstractFS
import unittest
import conpot
from freezegun import freeze_time
import fs
from datetime import datetime
from fs.time import epoch_to_datetime


class TestFileSystem(unittest.TestCase):
    """
    Tests related to Conpot's virtual file system.
    """

    def setUp(self):
        conpot_core.initialize_vfs()
        self.test_vfs = conpot_core.get_vfs()

    def tearDown(self):
        self.test_vfs.close()

    def test_listdir(self):
        _list = self.test_vfs.listdir(".")
        self.assertIn("data", _list)

    def test_chmod(self):
        # let us first create some directories!
        # TODO: check file create permissions and directory create permissions
        self.test_vfs.chmod("/data", 0o500, recursive=True)
        # Test that changes are reflected in the FS
        self.assertEqual(
            fs.permissions.Permissions.create(0o500),
            self.test_vfs.getinfo(path="/data", namespaces=["access"]).permissions,
        )
        # No changes made in the actual file system.
        self.assertNotEqual(
            fs.permissions.Permissions.create(0o500),
            self.test_vfs.getinfo(
                path="/data", get_actual=True, namespaces=["access"]
            ).permissions,
        )

    def test_chown(self):
        self.test_vfs.register_user(name="test_user", uid=3000)
        self.test_vfs.create_group(name="test_grp", gid=2000)
        # do chown
        self.test_vfs.chown("/data", uid=3000, gid=2000)
        # check uid
        self.assertEqual(
            self.test_vfs.getinfo("/data", namespaces=["access"]).uid, 3000
        )
        # actual uid shouldn't have changed
        self.assertNotEqual(
            self.test_vfs.getinfo("/data", get_actual=True, namespaces=["access"]).uid,
            3000,
        )
        # check gid
        self.assertEqual(
            self.test_vfs.getinfo("/data", namespaces=["access"]).gid, 2000
        )
        # FIXME: self.assertNotEqual(self.test_vfs.getinfo('/data', get_actual=True, namespaces=['access']).gid, 2000)
        # check file username
        self.assertEqual(
            self.test_vfs.getinfo("/data", namespaces=["access"]).user, "test_user"
        )
        self.assertNotEqual(
            self.test_vfs.getinfo("/data", get_actual=True, namespaces=["access"]).user,
            "test_user",
        )
        # check file group
        self.assertEqual(
            self.test_vfs.getinfo("/data", namespaces=["access"]).group, "test_grp"
        )
        self.assertNotEqual(
            self.test_vfs.getinfo(
                "/data", get_actual=True, namespaces=["access"]
            ).group,
            "test_grp",
        )
        # TODO: check for exceptions when user does not exist in the user/grp tables.

    def test_jail(self):
        """Test for checking chroot jail a subfilesystem"""
        # TODO: check for fs.error.permission denied error when we do a '../'
        self.assertTrue(self.test_vfs.create_jail("/data"))

    def test_mkdir(self):
        self.test_vfs.makedir("/dummy_dir", permissions=0o500)
        self.assertTrue(self.test_vfs.norm_path("/dummy_dir"))
        self.assertNotEqual(
            self.test_vfs.getinfo(
                "/dummy_dir", get_actual=True, namespaces=["access"]
            ).permissions,
            fs.permissions.Permissions.create(0o500),
        )
        # check the usr/grp that created the folder
        self.assertEqual(
            self.test_vfs.getinfo("/dummy_dir", namespaces=["access"]).uid,
            self.test_vfs.default_uid,
        )

    def test_open_dir(self):
        self.assertIsInstance(self.test_vfs.opendir("/data"), SubAbstractFS)

    def test_get_cwd(self):
        self.assertEqual("/", self.test_vfs.getcwd())

    @freeze_time("2018-07-15 17:51:17", tz_offset=-4)
    def test_snapshot(self):
        self.assertEqual(
            {"date-time", "snapshot-data"}, set(self.test_vfs.take_snapshot().keys())
        )
        self.assertEqual(
            self.test_vfs.take_snapshot()["date-time"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    @freeze_time("2018-07-15 17:51:17", tz_offset=-4)
    def test_stat(self):
        # TODO: Fix these to appropriate values -- check if the values are valid or not.
        # check if all relevant attributes exist in stat
        self.assertTrue(
            all(
                True if i in set(self.test_vfs.stat("/data").keys()) else False
                for i in {
                    "st_uid",
                    "st_gid",
                    "st_mode",
                    "st_atime",
                    "st_mtime",
                    "st_mtime_ns",
                    "st_ctime_ns",
                    "st_ctime",
                }
            )
        )

    @freeze_time("2018-07-15 17:51:17", tz_offset=-4)
    def test_getmtime(self):
        _mtime = self.test_vfs.getmtime("/data")
        self.assertFalse(_mtime == datetime.now())

    def test_get_permissions(self):
        self.assertEqual(
            self.test_vfs.getinfo("/data", namespaces=["access"]).permissions.as_str(),
            self.test_vfs.get_permissions("/data"),
        )

    def test_remove(self):
        self.test_vfs.touch("test_remove.txt")
        self.test_vfs.setinfo("test_remove.txt", {})
        self.test_vfs.remove("test_remove.txt")
        self.assertNotIn("test_remove.txt", self.test_vfs._cache.keys())

    def test_removedir(self):
        self.test_vfs.makedir("/dummy")
        self.test_vfs.removedir("/dummy")
        self.assertNotIn("/dummy", self.test_vfs._cache.keys())

    def test_readlink(self):
        self.assertIsNone(self.test_vfs.readlink("/data"))

    def test_mkdirs(self):
        self.test_vfs.makedirs("demo/demo")
        self.assertTrue(self.test_vfs.get_permissions("/demo/demo"))

    def test_openbin_file(self):
        with self.test_vfs.openbin("new_file", mode="wb") as _file:
            _file.write(b"This is just a test")
        self.assertIn("new_file", self.test_vfs.listdir("/"))
        _test = self.test_vfs.readtext("/new_file")
        self.test_vfs.getinfo("new_file", namespaces=["basic"])
        self.assertEqual(_test, "This is just a test")

    def test_open_file(self):
        with self.test_vfs.open("new_file", mode="w+") as _file:
            _file.write("This is just a test")
        self.assertIn("new_file", self.test_vfs.listdir("/"))
        _test = self.test_vfs.readtext("/new_file")
        self.test_vfs.getinfo("new_file", namespaces=["basic"])
        self.assertEqual(_test, "This is just a test")

    @freeze_time("2018-07-15 17:51:17")
    def test_format_list(self):
        self.test_vfs.settimes(
            "/data", accessed=datetime.now(), modified=datetime.now()
        )
        self._f_list = self.test_vfs.format_list("/", self.test_vfs.listdir("/"))
        [_result] = [i for i in self._f_list]
        self.assertIn("root", _result)
        self.assertIn("Jul 15 17:51", _result)

    @freeze_time("2028-07-15 17:51:17")
    def test_utime(self):
        self.test_vfs.utime("/data", accessed=datetime.now(), modified=datetime.now())
        self.assertEqual(
            self.test_vfs.getinfo("/data", namespaces=["details"]).modified.ctime(),
            datetime.now().ctime(),
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data", namespaces=["details"]).accessed.ctime(),
            datetime.now().ctime(),
        )

    def test_access(self):
        # check it the root user has all the permissions
        self.assertTrue(self.test_vfs.access("/data", 0, required_perms="rwx"))
        # create some random group and check permissions for that
        self.test_vfs.create_group("random", 220)
        self.assertFalse(self.test_vfs.access("/data", "random", required_perms="x"))

    @freeze_time("2028-07-15 17:51:17")
    def test_movedir(self):
        # move a directory - retain it's contents
        _uid = self.test_vfs.getinfo("/data", namespaces=["access"]).uid
        _gid = self.test_vfs.getinfo("/data", namespaces=["access"]).gid
        _perms = self.test_vfs.getinfo("/data", namespaces=["access"]).permissions
        _user = self.test_vfs.getinfo("/data", namespaces=["access"]).user
        _group = self.test_vfs.getinfo("/data", namespaces=["access"]).group
        _accessed = self.test_vfs.getinfo("/data", namespaces=["details"]).accessed
        _modified = self.test_vfs.getinfo("/data", namespaces=["details"]).modified
        self.test_vfs.movedir("/data", "/data_move", create=True)
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).uid, _uid
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).gid, _gid
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).permissions,
            _perms,
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).user, _user
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).group, _group
        )
        # accessed and modified file must not be the same.
        self.test_vfs.settimes(
            "/data_move", accessed=datetime.now(), modified=datetime.now()
        )
        self.assertNotEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["details"]).accessed,
            _accessed,
        )
        self.assertNotEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["details"]).modified,
            _modified,
        )

    @freeze_time("2028-07-15 17:51:17")
    def test_copydir(self):
        # copy a directory
        _uid = self.test_vfs.getinfo("/data", namespaces=["access"]).uid
        _gid = self.test_vfs.getinfo("/data", namespaces=["access"]).gid
        _perms = self.test_vfs.getinfo("/data", namespaces=["access"]).permissions
        _user = self.test_vfs.getinfo("/data", namespaces=["access"]).user
        _group = self.test_vfs.getinfo("/data", namespaces=["access"]).group
        self.test_vfs.copydir("/data", "/data_move", create=True)
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).uid, _uid
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).gid, _gid
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).permissions,
            _perms,
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).user, _user
        )
        self.assertEqual(
            self.test_vfs.getinfo("/data_move", namespaces=["access"]).group, _group
        )
        self.assertEqual(set(self.test_vfs.listdir("/")), {"data", "data_move"})

    @freeze_time("2028-07-15 17:51:17")
    def test_copyfile(self):
        # create a copy of a file in a separate directory
        with self.test_vfs.open("test_fs.txt", mode="w+") as _file:
            _file.write("This is just a test file checking copyfile")
        self.test_vfs.copy(
            src_path="test_fs.txt", dst_path="test_fs_copy.txt", overwrite=True
        )
        _text = self.test_vfs.readtext("test_fs_copy.txt")
        self.assertEqual(_text, "This is just a test file checking copyfile")
        self.assertTrue(self.test_vfs.getbasic("test_fs_copy.txt"))

    @freeze_time("2028-07-15 17:51:17")
    def test_movefile(self):
        # create a copy of a file in a separate directory
        with self.test_vfs.open("test_fs.txt", mode="w") as _file:
            _file.write("This is just a test file checking copyfile")
        _uid = self.test_vfs.getinfo("test_fs.txt", namespaces=["access"]).uid
        self.test_vfs.move("test_fs.txt", "test_fs_copy.txt", overwrite=True)
        _text = self.test_vfs.readtext("test_fs_copy.txt")
        self.assertEqual(
            self.test_vfs.getinfo("test_fs_copy.txt", namespaces=["access"]).uid, _uid
        )
        self.assertEqual(_text, "This is just a test file checking copyfile")


class TestSubFileSystem(unittest.TestCase):
    """
    Tests related to Conpot's virtual sub file system. This would test fs generated folders for each and
    every protocol.
    """

    def setUp(self):
        conpot_core.initialize_vfs()
        self._vfs = conpot_core.get_vfs()
        self._vfs.register_user("test_user", 13)
        self._vfs.create_group("test_grp", 13)
        self.test_vfs = self._vfs.mount_fs(
            fs_url="/".join(conpot.__path__ + ["tests/data/test_data_fs/vfs"]),
            dst_path="/data",
            owner_uid=13,
            group_gid=13,
            perms=0o750,
        )

    def tearDown(self):
        self._vfs.close()

    def test_listdir(self):
        _list = self.test_vfs.listdir(".")
        self.assertIn("vfs.txt", _list)

    def test_chmod(self):
        self.test_vfs.chmod("vfs.txt", 0o500, recursive=True)
        # Test that changes are reflected in the FS
        self.assertEqual(
            fs.permissions.Permissions.create(0o500),
            self.test_vfs.getinfo(path="vfs.txt", namespaces=["access"]).permissions,
        )
        # No changes made in the actual file system.
        self.assertNotEqual(
            fs.permissions.Permissions.create(0o500),
            self.test_vfs.getinfo(
                path="vfs.txt", get_actual=True, namespaces=["access"]
            ).permissions,
        )

    def test_chown(self):
        self.test_vfs.register_user(name="new_user", uid=3000)
        self.test_vfs.create_group(name="new_grp", gid=2000)
        # do chown
        self.test_vfs.chown("vfs.txt", uid=3000, gid=2000)
        # check uid
        self.assertEqual(
            self.test_vfs.getinfo("vfs.txt", namespaces=["access"]).uid, 3000
        )
        # actual uid shouldn't have changed
        self.assertNotEqual(
            self.test_vfs.getinfo(
                "vfs.txt", get_actual=True, namespaces=["access"]
            ).uid,
            3000,
        )

    def test_mkdir(self):
        self.test_vfs.makedir("/dummy", permissions=0o500)
        self.assertFalse(
            self.test_vfs.access("/dummy", self.test_vfs.default_uid, "rwx")
        )
        self.test_vfs.removedir("/dummy")
        self.assertNotIn("/dummy", self.test_vfs._cache.keys())

    def test_mkdirs(self):
        self.test_vfs.makedirs("/demo/demo")
        self.assertTrue(self.test_vfs.get_permissions("/demo/demo"))

    @freeze_time("2018-07-17 17:51:17")
    def test_open_file(self):
        with self.test_vfs.open("new_file", mode="wb") as _file:
            _file.write(b"This is just a test")
        self.assertIn("new_file", self.test_vfs.listdir("/"))
        self.test_vfs.settimes(
            "/new_file", accessed=datetime.now(), modified=datetime.now()
        )
        _test = self.test_vfs.readtext("/new_file")
        self.assertEqual(_test, "This is just a test")
        self.assertEqual(
            self.test_vfs.getinfo("new_file", namespaces=["details"]).modified.ctime(),
            datetime.now().ctime(),
        )

    def test_get_cwd(self):
        self.assertEqual(self.test_vfs.getcwd(), "/data")

    @freeze_time("2028-07-15 17:51:17")
    def test_utime(self):
        self.test_vfs.utime("vfs.txt", accessed=datetime.now(), modified=datetime.now())
        self.assertEqual(
            self.test_vfs.getinfo("vfs.txt", namespaces=["details"]).modified.ctime(),
            datetime.now().ctime(),
        )
        self.assertEqual(
            self.test_vfs.getinfo("vfs.txt", namespaces=["details"]).accessed.ctime(),
            datetime.now().ctime(),
        )

    @freeze_time("2018-07-15 17:51:17", tz_offset=-4)
    def test_stat(self):
        # TODO: Fix these to appropriate values -- check if the values are valid or not.
        # check if all relevant attributes exist in stat
        self.assertTrue(
            all(
                True if i in set(self.test_vfs.stat("vfs.txt").keys()) else False
                for i in {
                    "st_uid",
                    "st_gid",
                    "st_mode",
                    "st_atime",
                    "st_mtime",
                    "st_mtime_ns",
                    "st_ctime_ns",
                    "st_ctime",
                }
            )
        )

    def test_get_permissions(self):
        self.assertEqual(
            self.test_vfs.getinfo(
                "vfs.txt", namespaces=["access"]
            ).permissions.as_str(),
            self.test_vfs.get_permissions("vfs.txt"),
        )

    @freeze_time("2018-07-15 17:51:17")
    def test_set_time(self):
        """Test for changing time in the file system."""
        self.test_vfs.settimes(
            "vfs.txt",
            accessed=epoch_to_datetime(103336010),
            modified=epoch_to_datetime(103336010),
        )
        self.assertEqual(
            self.test_vfs.getinfo("vfs.txt", namespaces=["details"]).accessed,
            epoch_to_datetime(103336010),
        )
        self.assertEqual(
            self.test_vfs.getinfo("vfs.txt", namespaces=["details"]).modified,
            epoch_to_datetime(103336010),
        )

    def test_access(self):
        # check it the root user has all the permissions
        self.assertFalse(self.test_vfs.access("/vfs.txt", 0, required_perms="rwx"))
        self.assertEqual(
            self.test_vfs.getinfo("/vfs.txt", namespaces=["access"]).uid, 13
        )
        self.assertTrue(self.test_vfs.access("/vfs.txt", 13, required_perms="rwx"))
        # create some random group and check permissions for that
        self.test_vfs.create_group("random", 220)
        self.assertFalse(self.test_vfs.access("/vfs.txt", "random", required_perms="x"))
        # create a new user called test_access and add it group with gid 13
        self.test_vfs.register_user("test_access", 45)
        self.test_vfs.add_users_to_group(13, [45])
        self.assertTrue(self.test_vfs.access("/vfs.txt", 45, required_perms="rx"))
        self.assertFalse(self.test_vfs.access("/vfs.txt", 45, required_perms="rwx"))

    def test_remove(self):
        self.test_vfs.touch("test_remove.txt")
        self.test_vfs.setinfo("test_remove.txt", {})
        self.test_vfs.remove("test_remove.txt")
        self.assertNotIn("test_remove.txt", self.test_vfs._cache.keys())

    def test_removedir(self):
        self.test_vfs.makedir("/dummy")
        self.test_vfs.removedir("/dummy")
        self.assertNotIn("/dummy", self.test_vfs._cache.keys())

    def test_readlink(self):
        # FIXME: add tests for a file that is actually a link!
        self.assertIsNone(self.test_vfs.readlink("vfs.txt"))

    @freeze_time("2018-07-15 17:51:17")
    def test_format_list(self):
        self.test_vfs.settimes(
            "vfs.txt", accessed=datetime.now(), modified=datetime.now()
        )
        self._f_list = self.test_vfs.format_list("/", self.test_vfs.listdir("/"))
        [_result] = [i for i in self._f_list]
        self.assertIn(self.test_vfs.default_user, _result)
        self.assertIn("Jul 15 17:51", _result)
