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

import time
"""
Central Authentication mechanism. To maintain consistencies b/w users, groups and vfs.
"""

# FIXME: must use context manager - __enter__() and __exit__() for vfs. Something like
#   with run_with_access(user='', grp='', perms=''):
#     with vfs.open('file.txt', mode='w') as _file:
#         _file.write('Hello!')
# It should automatically create files - do chmod and chown - raise PermissionsException and other exceptions,
# update the cache including accessed and modified time - and close the file after use.


class ConpotAuthenticationException(Exception):
    pass


class AuthUserDB(object):
    """
        Class to handle-create-maintain virtual users.

        Central authentication system provides more consistency. Protocols should be able to query this auth
        module and verify the user/pass pairs. This ensures that all users within Conpot reflect the same
        permissions/users etc.
    """

    def __init__(self, config=None, hash_type='plaintext'):
        # TODO: In future we want to attach rainbow tables to conpot.
        # Currently we are only verifying passwords that are plaintext.
        self._user_db = dict()
        self._grp_db = dict()
        # we must have at least one user as default in Conpot. Let us add root
        self._user_db[0] = {
            'scope': 'global',         # |--> Global access would allow these users from all protocols.
            'user': 'root',
            'grp': '0:nobody',         # |--> This entry would be popped out as grp_db is populated.
            'password': '<0nPot',
            'created': time.ctime(),   # |--> No special significance just for logging purposes.
            'last_login': None,
            'protocol': None
        }
        # create a simple set of (user, pass) tuple combinations for easy auth
        self.user_pass = lambda: set(zip([v['user'] for v in self._user_db.values()],
                                         [v['password'] for v in self._user_db.values()]))
        # self._init_user_db(file=config)
        self._generate_grps()

    def protocol_users(self, protocol_name):
        """
        :param protocol_name: Name of the protocol.
        :return: Get the list of all users that are registered with a particular protocol.
        """
        [_proto_users] = [i for i in self._user_db.keys() if (self._user_db[i]['protocol'] == protocol_name or
                                                              self._user_db[i]['scope'] == 'global')]
        return _proto_users

    def _generate_grps(self):
        # Create groups from the populated users.
        for i in self._user_db.keys():
            if 'grp' in self._user_db.values():
                grp = self._user_db[i].pop('grp')
                _gid, _gname = grp.split(':')
                _gid = int(_gid)
                if _gid not in self._user_db.keys():
                    # It is a new group. Let us create/register this.
                    self._grp_db[_gid] = {'group': _gname, 'users': set()}
                self._grp_db[_gid]['users'].add(i)

    def add_user(self, user_info: str, protocol: str, scope: str):
        """
        Add users to the central auth system.
        :param user_info: Information provided should be of the following format:
        'uid:user_name:gid:grp_name:passwd'
        :param protocol: The protocol for which we are doing auth.
        :param scope: Whether we want this user_auth to be available in entire conpot?
        """
        if scope not in ('local', 'global'):
            raise ConpotAuthenticationException('scope must be either "local" or "global"')
        try:
            _info = user_info.split(':')
            assert len(_info) == 5
            _uid = int(_info[0])
            self._user_db[_uid] = {
                'user': _info[1],
                'password': _info[4],
                'created': time.ctime(),
                'last_login': None,
                'protocol': protocol
            }
            if scope is 'global':
                self._user_db[_uid]['scope'] = 'global'
            else:
                self._user_db[_uid]['scope'] = 'local'
            # add to the grp_db
            if int(_info[2]) not in self._grp_db.keys():
                # It is a new group. Let us create/register this.
                self._grp_db[int(_info[2])] = {'group': _info[3], 'users': set()}
            self._grp_db[int(_info[2])]['users'].add(_uid)
        except (KeyError, AssertionError) as err:
            raise ConpotAuthenticationException('Error occurred while adding {} to Conpot auth module: {}'.format(
                (user_info, protocol, scope), err
            ))

    def authentication_ok(self, user: str, passwd: str, protocol: str):
        """
        :param user: username of the user to be authenticated.
        :param passwd: password of the user to be authenticated.
        :param protocol: Name of the protocol requesting authentication
        :return: return True if user/pass is valid, else false.
        """
        auth = bool((user, passwd) in self.user_pass())
        if auth:
            # check whether the cred has global access or is registered with a protocol
            if user in self.protocol_users(protocol):
                # update the last login time:
                self._user_db[self.get_uid(user_name=user)]['last_login'] = time.ctime()
                return True
            return False
        return False

    def remove_user(self, uid):
        pass

    def remove_grp(self):
        pass

    def get_user_group(self):
        """Get the grp name of the current user"""
        pass

    def get_uid(self, user_name):
        """Get uid from user name"""
        [_uid] = [i for i in self._user_db.keys() if self._user_db[i]['user'] == user_name]
        return _uid


class RandomAuthUserDB(AuthUserDB):
    """
        Add random users with specified permissions when multiple brute-force attempts are being being made by the
        same IP address.
    """
    pass