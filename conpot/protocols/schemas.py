from schema import Optional, Or, Schema

tftp = Schema(
    {
        "tftp": {
            "enabled": bool,
            "host": str,
            "port": int,
            "tftp_root_path": str,
            "add_src": str,
            "data_fs_subdir": str,
        }
    }
)

guardian_ast = Schema(
    {
        "guardian_ast": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("device_info"): {
                Optional("vendor_name"): str,
                Optional("product_code"): str,
            },
        }
    }
)

dnp3 = Schema(
    {
        "dnp3": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("timeout"): Or(int, float),
            Optional("outstation_address"): int,
            Optional("master_address"): int,
            Optional("unsolicited_enabled"): bool,
            Optional("device_info"): {
                Optional("vendor_name"): str,
                Optional("product_code"): str,
            },
            Optional("binary_inputs"): [
                {
                    "index": int,
                    Optional("value"): bool,
                }
            ],
            Optional("analog_inputs"): [
                {
                    "index": int,
                    Optional("value"): Or(int, float),
                }
            ],
        }
    }
)

kamstrup_management = Schema(
    {
        "kamstrup_management": {
            "enabled": bool,
            "host": str,
            "port": int,
        }
    }
)

ipmi = Schema(
    {
        "ipmi": {
            "enabled": bool,
            "host": str,
            "port": int,
            "device_info": {"device_name": str},
            "user_list": [
                {
                    "user_name": str,
                    "password": str,
                    "privilege": int,
                    "active": bool,
                    "fixed": bool,
                }
            ],
        }
    }
)

enip = Schema(
    {
        "enip": {
            "enabled": bool,
            "host": str,
            "port": int,
            "mode": str,
            "latency": Or(int, float),
            "timeout": Or(int, float),
            "device_info": {
                "VendorId": int,
                "ProductName": str,
                "DeviceType": int,
                "SerialNumber": Or(str, int),
                "ProductRevision": int,
                "ProductCode": int,
            },
            "tags": [
                {
                    "name": str,
                    "type": str,
                    "size": int,
                    "value": Or(str, int, float),
                    "addr": str,
                }
            ],
        }
    }
)

kamstrup_meter = Schema(
    {
        "kamstrup_meter": {
            "enabled": bool,
            "host": str,
            "port": int,
            "communication_address": int,
            "registers": [
                {
                    "name": int,
                    "length": int,
                    "units": int,
                    "unknown": int,
                    "value": str,
                }
            ],
        }
    }
)

bacnet = Schema(
    {
        "bacnet": {
            "enabled": bool,
            "host": str,
            "port": int,
            "device_info": dict,
            Optional("object_list"): [
                {
                    "name": str,
                    "properties": dict,
                }
            ],
        }
    }
)

s7comm = Schema(
    {
        "s7comm": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("system_status_lists"): [
                {
                    "id": str,
                    "name": str,
                    "items": [
                        {
                            "id": str,
                            Optional("name"): str,
                            Optional("value"): str,
                        }
                    ],
                }
            ],
            Optional("memory_areas"): [
                {
                    "type": str,
                    "name": str,
                    Optional("number"): int,
                    Optional("size"): int,
                }
            ],
        }
    }
)

modbus = Schema(
    {
        "modbus": {
            "enabled": bool,
            "host": str,
            "port": int,
            "mode": str,
            "delay": int,
            Optional("umas_enabled"): bool,
            "device_info": {
                "VendorName": str,
                "ProductCode": str,
                "MajorMinorRevision": str,
            },
            "slaves": [
                {
                    "id": int,
                    "blocks": [
                        {
                            "name": str,
                            "type": str,
                            "starting_address": int,
                            "size": int,
                            Optional("content"): str,
                        }
                    ],
                }
            ],
        }
    }
)

IEC104 = Schema(
    {
        "IEC104": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("device_info"): dict,
            "categories": [
                {
                    "name": str,
                    "id": int,
                    "registers": [
                        {
                            "name": str,
                            "value": str,
                            Optional("rel"): str,
                        }
                    ],
                }
            ],
        }
    }
)

snmp = Schema(
    {
        "snmp": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("config"): [
                {
                    "name": str,
                    "command": str,
                    "value": str,
                }
            ],
            Optional("mibs"): [
                {
                    "name": str,
                    "symbols": [
                        {
                            "name": str,
                            "value": str,
                            Optional("instance"): str,
                        }
                    ],
                }
            ],
        }
    }
)

ftp = Schema(
    {
        "ftp": {
            "enabled": bool,
            "host": str,
            "port": int,
            "device_info": dict,
            "ftp_users": dict,
            "ftp_vfs": dict,
        }
    }
)

http = Schema(
    {
        "http": {
            "enabled": bool,
            "host": str,
            "port": int,
            "global": dict,
            Optional("htdocs"): [dict],
            Optional("statuscodes"): [dict],
        }
    }
)

proxies = Schema(
    {
        "proxies": {
            "enabled": bool,
            "proxy": [
                {
                    "name": str,
                    "host": str,
                    "port": int,
                    "proxy_host": str,
                    "proxy_port": int,
                    Optional("decoder"): str,
                    Optional("keyfile"): str,
                    Optional("certfile"): str,
                }
            ],
        }
    }
)

goose = Schema(
    {
        "goose": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("appid"): int,
            Optional("gocb_ref"): str,
            Optional("dat_set"): str,
            Optional("go_id"): str,
            Optional("conf_rev"): int,
            Optional("time_allowed_to_live"): int,
            Optional("st_num"): int,
            Optional("sq_num"): int,
            Optional("spdu_number"): int,
            Optional("publish_interval_ms"): Or(int, float),
            Optional("publish_dest"): str,
            Optional("publish_dest_port"): int,
            Optional("multicast_group"): str,
            Optional("all_data"): [
                Or(
                    {"boolean": bool},
                    {"integer": int},
                )
            ],
        }
    }
)

iccp = Schema(
    {
        "iccp": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("timeout"): Or(int, float),
            Optional("vendor"): str,
            Optional("model"): str,
            Optional("revision"): str,
            Optional("domain"): str,
            Optional("points"): [
                {
                    "name": str,
                    Optional("type"): Or("boolean", "integer", "float"),
                    Optional("value"): Or(bool, int, float),
                }
            ],
        }
    }
)

opcua = Schema(
    {
        "opcua": {
            "enabled": bool,
            "host": str,
            "port": int,
            Optional("timeout"): Or(int, float),
            Optional("endpoint_path"): str,
            Optional("server_name"): str,
            Optional("namespace_uri"): str,
            Optional("application_uri"): str,
            Optional("variables"): [
                {
                    "name": str,
                    Optional("type"): Or("boolean", "integer", "float", "string"),
                    Optional("value"): Or(bool, int, float, str),
                }
            ],
        }
    }
)
