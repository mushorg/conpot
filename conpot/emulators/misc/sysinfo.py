import socket
import psutil
from datetime import datetime


class CpuLoad:
    def get_value(self):
        return psutil.cpu_percent()


class TotalRam:
    def get_value(self):
        return psutil.virtual_memory().total / 1024


class StorageSize:
    def get_value(self):
        return psutil.disk_usage("/").total / 1024


class StorageUsed:
    def get_value(self):
        return psutil.disk_usage("/").used / 1024


class BootTime:
    def get_value(self):
        return int(datetime.now().timestamp() - psutil.boot_time())


class CurrentDatetime:
    def get_value(self):
        return datetime.now().strftime("%Y-%m-%d,%H:%M:%S.0")


class LocalIP:
    def get_value(self):
        return socket.gethostbyname(socket.gethostname())


class PacketsSent:
    def get_value(self):
        return psutil.net_io_counters().packets_sent


class PacketsRecv:
    def get_value(self):
        return psutil.net_io_counters().packets_recv


class BytesSent:
    def get_value(self):
        return psutil.net_io_counters().bytes_sent


class BytesRecv:
    def get_value(self):
        return psutil.net_io_counters().bytes_recv


class TcpCurrEstab:
    def get_value(self):
        return len(
            [
                conn
                for conn in psutil.net_connections("tcp")
                if conn.status in (psutil.CONN_ESTABLISHED, psutil.CONN_CLOSE_WAIT)
            ]
        )
