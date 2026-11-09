from tools.conpot_cloner import parse_report_slave_id, render_modbus_toml


def test_parse_report_slave_id_extracts_identifier_and_additional_data():
    assert parse_report_slave_id(b"\x11\x06\x09\xffM340") == ("09", "4d333430")
    assert parse_report_slave_id(b"\x11\x06\x09\x00M340") == ("09", "4d333430")


def test_parse_report_slave_id_rejects_malformed_response():
    assert parse_report_slave_id(b"\x11\x07\x09\xffM340") is None
    assert parse_report_slave_id(b"\x11\x06\x09\x01M340") is None


def test_parse_report_slave_id_preserves_non_status_additional_data():
    assert parse_report_slave_id(b"\x11\x06\x09\xffM34\x01") == (
        "09",
        "4d333401",
    )


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
                "report_slave_id": "09",
                "report_slave_id_additional_data": "4d333430",
                "blocks": [],
            }
        ],
        502,
    )

    assert 'ReportSlaveId = "09"' in text
    assert 'ReportSlaveIdAdditionalData = "4d333430"' in text


def test_render_modbus_toml_keeps_different_ids_per_unit():
    text, _databus = render_modbus_toml(
        [
            {
                "id": 1,
                "report_slave_id": "09",
                "report_slave_id_additional_data": "41",
                "blocks": [],
            },
            {
                "id": 2,
                "report_slave_id": "0a",
                "report_slave_id_additional_data": "42",
                "blocks": [],
            },
        ],
        502,
    )

    units = text.split("[[modbus.slaves]]")[1:]
    assert 'ReportSlaveId = "09"' in units[0]
    assert 'ReportSlaveIdAdditionalData = "41"' in units[0]
    assert 'ReportSlaveId = "0a"' in units[1]
    assert 'ReportSlaveIdAdditionalData = "42"' in units[1]
