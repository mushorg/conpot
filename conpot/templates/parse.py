import tomllib


def parse_toml_config(toml_file):
    with open(toml_file, "rb") as handle:
        return tomllib.load(handle)
