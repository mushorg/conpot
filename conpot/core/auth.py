"""
Central Authentication mechanism. To maintain consistencies b/w users, groups and
"""


class AuthUserDB(object):
    """
        Class to handle-create-maintain virtual users.

        Central authentication system provides more consistency. Protocols should be able to query this auth
        module and verify the user/pass pairs. This ensures that all users within Conpot reflect the same
        permissions/users etc.
    """
    def __int__(self):
        pass

    def add_user(self):
        pass

    def remove_user(self):
        pass

    def add_grp(self):
        pass

    def remove_grp(self):
        pass

    def get_user_group(self):
        """Get the grp name of the current user"""
        pass

    def set_user_group(self):
        pass

    def verify_user(self):
        """Auth"""
        pass

    def get_home_dir(self):
        pass

    def message_login(self):
        """Login message - protocol specific."""
        raise NotImplemented

    def message_quit(self):
        """message when an user quits - protocol specific"""
        raise NotImplemented


class RandomAuthUserDB(AuthUserDB):
    """
        Add random users with specified permissions when multiple brute-force attempts are being being made by the
        same IP address.
    """
    pass