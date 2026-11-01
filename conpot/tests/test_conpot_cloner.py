from tools.conpot_cloner import parse_report_slave_id, render_modbus_toml


def test_parse_report_slave_id_extracts_identifier_and_additional_data():
    assert parse_report_slave_id(b"\x11\x06\x09M340\xff") == "094d333430"


def test_parse_report_slave_id_rejects_malformed_response():
    assert parse_report_slave_id(b"\x11\x07\x09M340\xff") is None
    assert parse_report_slave_id(b"\x11\x06\x09M340\x01") is None


def test_render_modbus_toml_emits_cloned_report_slave_id():
    text, _databus = render_modbus_toml(
        [
            {
                "id": 1,
                "device_info": {
                    "VendorName": "Schneider Electric",
                    "ProductCode": "Modicon M340",
                    "MajorMinorRevision": "1.0",
                },
                "report_slave_id": "094d333430",
                "blocks": [],
            }
        ],
        502,
    )

    assert 'ReportSlaveId = "094d333430"' in text
