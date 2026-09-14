from schema import Schema

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
