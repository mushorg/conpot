from conpot.core.protocol_wrapper import conpot_protocol


@conpot_protocol
class ProtocolFake:
    """Fake docstring"""

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"ProtocolFake({self.value})"


def test_instances_have_separate_fields():
    inst_1 = ProtocolFake(1)
    inst_2 = ProtocolFake(2)

    assert inst_1.value == 1
    assert inst_2.value == 2


def test_instances_have_separate_repr():
    inst_1 = ProtocolFake(1)
    inst_2 = ProtocolFake(2)

    assert repr(inst_1) == "ProtocolFake(1)"
    assert repr(inst_2) == "ProtocolFake(2)"


def test_wrapped_classes_have_inner_class_attributes():
    assert ProtocolFake.__doc__ == "Fake docstring"
    assert ProtocolFake.__module__ == __name__
    assert ProtocolFake.__name__ == "ProtocolFake"
