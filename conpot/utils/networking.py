import socket
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


def get_interface_ip(destination_ip: str):
    # returns interface ip from socket in case direct udp socket access not possible
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((destination_ip, 80))
    socket_ip = s.getsockname()[0]
    s.close()
    return socket_ip
