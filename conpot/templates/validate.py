from schema import Schema, And

base_schema = Schema(
    {
        "core": {
            "template": {
                "unit": And(str, len),
                "vendor": And(str, len),
                "description": And(str, len),
                "protocols": And(list, len),
                "creator": And(str, len),
            },
            "databus": {"key_value_mappings": object},
        },
    }
)


def validate_toml_template(template, schema):
    schema.validate(template)
