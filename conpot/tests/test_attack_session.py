from datetime import datetime, timedelta

from freezegun import freeze_time

from conpot.core.attack_session import AttackSession


class LogQueueFake:
    def __init__(self):
        self.events = []

    def put(self, event):
        self.events.append(event)


def test_add_event_is_logged():
    protocol = "testing"
    source_ip = "1.2.3.4"
    source_port = 11
    destination_ip = "5.6.7.8"
    destination_port = 22
    log_queue = LogQueueFake()

    session = AttackSession(
        protocol=protocol,
        source_ip=source_ip,
        source_port=source_port,
        destination_ip=destination_ip,
        destination_port=destination_port,
        log_queue=log_queue,
    )

    event = {"foo": "bar"}
    session.add_event(event)

    logged = log_queue.events[0]
    assert logged["data"] == event
    assert logged["data_type"] == protocol

    assert logged["src_ip"] == source_ip
    assert logged["src_port"] == source_port
    assert logged["remote"] == (source_ip, source_port)

    assert logged["dst_ip"] == destination_ip
    assert logged["dst_port"] == destination_port
    assert logged["local"] == (destination_ip, destination_port)

    # TODO should this even include public_ip if it's always None?
    assert logged["public_ip"] is None


def test_add_event_same_id():
    log_queue = LogQueueFake()

    session = AttackSession(
        protocol=None,
        source_ip=None,
        source_port=None,
        destination_ip=None,
        destination_port=None,
        log_queue=log_queue,
    )

    session.add_event({"foo": "bar"})
    session.add_event({"bar": "baz"})

    assert log_queue.events[0]["id"] == log_queue.events[1]["id"]


def test_add_event_sessions_have_unique_ids():
    log_queue = LogQueueFake()

    session_1 = AttackSession(
        protocol=None,
        source_ip=None,
        source_port=None,
        destination_ip=None,
        destination_port=None,
        log_queue=log_queue,
    )

    session_2 = AttackSession(
        protocol=None,
        source_ip=None,
        source_port=None,
        destination_ip=None,
        destination_port=None,
        log_queue=log_queue,
    )

    session_1.add_event({"foo": "bar"})
    session_2.add_event({"bar": "baz"})

    assert log_queue.events[0]["id"] != log_queue.events[1]["id"]


def test_add_event_uses_session_timestamp():
    log_queue = LogQueueFake()
    session_start = datetime(2000, 1, 1)

    with freeze_time(session_start) as frozen_time:
        session = AttackSession(
            protocol=None,
            source_ip=None,
            source_port=None,
            destination_ip=None,
            destination_port=None,
            log_queue=log_queue,
        )

        frozen_time.tick(timedelta(days=1))
        session.add_event({"foo": "bar"})
        session.add_event({"bar": "baz"})

        # timestamp is always the time the session started,
        # not the time the event occurred
        assert log_queue.events[0]["timestamp"] == session_start
        assert log_queue.events[1]["timestamp"] == session_start


@freeze_time("2000-01-01", auto_tick_seconds=2)
def test_dump_collects_events():
    protocol = "testing"
    source_ip = "1.2.3.4"
    source_port = 11
    destination_ip = "5.6.7.8"
    destination_port = 22
    log_queue = LogQueueFake()

    session = AttackSession(
        protocol=protocol,
        source_ip=source_ip,
        source_port=source_port,
        destination_ip=destination_ip,
        destination_port=destination_port,
        log_queue=log_queue,
    )

    event_1 = {"foo": "bar"}
    event_2 = {"bar": "baz"}

    session.add_event(event_1)
    session.add_event(event_2)
    session.add_event(event_1)

    dump = session.dump()

    assert dump["data_type"] == protocol
    assert list(dump["data"].keys()) == [2000, 4000, 6000]
    assert list(dump["data"].values()) == [event_1, event_2, event_1]

    assert dump["src_ip"] == source_ip
    assert dump["src_port"] == source_port
    assert dump["remote"] == (source_ip, source_port)

    assert dump["dst_ip"] == destination_ip
    assert dump["dst_port"] == destination_port
    assert dump["local"] == (destination_ip, destination_port)

    # TODO should this even include public_ip if it's always None?
    assert dump["public_ip"] is None
