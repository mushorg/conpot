"""
Some python3 fixtures - helper methods for handy conversions + fix ssl
"""
from datetime import datetime
from slugify import slugify


def sanitize_file_name(name, host, port):
    """
    Ensure that file_name is legal. Slug the filename and store it onto the server.
    This would ensure that there are no duplicates as far as writing a file is concerned. Also client addresses are
    noted so that one can verify which client uploaded the file.
    :param name: Name of the file
    :param host: host/client address
    :param port port/client port
    :type name: str
    """
    return (
        "("
        + host
        + ", "
        + str(port)
        + ")-"
        + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        + "-"
        + slugify(name)
    )


# py3 chr
def chr_py3(x):
    return bytearray((x,))


# convert a string to an ascii byte string
def str_to_bytes(x):
    return x if isinstance(x, bytes) else str(x).encode("ascii")


months_map = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


# https://www.bountysource.com/issues/4335201-ssl-broken-for-python-2-7-9
# Kudos to Eugene for this workaround!
def fix_sslwrap():
    # Re-add sslwrap to Python 2.7.9
    import inspect

    __ssl__ = __import__("ssl")

    try:
        _ssl = __ssl__._ssl
    except AttributeError:
        _ssl = __ssl__._ssl2

    def new_sslwrap(
        sock,
        server_side=False,
        keyfile=None,
        certfile=None,
        cert_reqs=__ssl__.CERT_NONE,
        ssl_version=__ssl__.PROTOCOL_SSLv23,
        ca_certs=None,
        ciphers=None,
    ):
        context = __ssl__.SSLContext(ssl_version)
        context.verify_mode = cert_reqs or __ssl__.CERT_NONE
        if ca_certs:
            context.load_verify_locations(ca_certs)
        if certfile:
            context.load_cert_chain(certfile, keyfile)
        if ciphers:
            context.set_ciphers(ciphers)

        caller_self = inspect.currentframe().f_back.f_locals["self"]
        return context._wrap_socket(sock, server_side=server_side, ssl_sock=caller_self)

    if not hasattr(_ssl, "sslwrap"):
        _ssl.sslwrap = new_sslwrap
