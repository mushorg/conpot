import toml


def parse_toml_config(toml_file):
    return toml.load(toml_file)
