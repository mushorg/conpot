import toml

from schema import Schema, And
from lxml import etree


def validate_xml_template(xml_file, xsd_file, logger):
    xml_schema = etree.parse(xsd_file)
    xsd = etree.XMLSchema(xml_schema)
    xml = etree.parse(xml_file)
    if not xsd.validate(xml):
        raise ValueError(xsd.error_log)


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
