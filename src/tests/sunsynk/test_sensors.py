"""Sunsynk sensor tests."""

import logging
from collections.abc import Iterable, Sequence
from itertools import pairwise

import pytest

from sunsynk.definitions.single_phase import AMPS, CELSIUS, SENSORS, VOLT, WATT
from sunsynk.sensors import (
    BinarySensor,
    FaultSensor,
    InverterStateSensor,
    MathSensor,
    SDStatusSensor,
    Sensor,
    Sensor16,
    SerialSensor,
    TempSensor,
)
from sunsynk.state import InverterState, group_sensors

_LOGGER = logging.getLogger(__name__)


def test_binary_sensor(state: InverterState) -> None:
    """Tests."""
    a = Sensor(194, "Grid Connected Status")  # Remove in the future?
    b = BinarySensor(194, "Grid Connected")
    state.track(a)
    state.track(b)
    # b = BinarySensor(111, "B 1")
    assert b.reg_to_value((0,)) is False
    assert b.reg_to_value((1,)) is True
    assert b.reg_to_value((2,)) is True
    assert b.reg_to_value((255,)) is True

    state.update({194: 2})
    assert hash(a) != hash(b)
    assert state.get(a) == 2
    assert state.get(b) is True

    state.update({194: 0})
    assert state[b] is False

    b = BinarySensor(111, "B 1", on=1)
    assert b.reg_to_value((0,)) is False
    assert b.reg_to_value((1,)) is True
    assert b.reg_to_value((2,)) is False
    assert b.reg_to_value((255,)) is False

    b = BinarySensor(111, "B 1", off=2)
    assert b.reg_to_value((0,)) is True
    assert b.reg_to_value((1,)) is True
    assert b.reg_to_value((2,)) is False
    assert b.reg_to_value((255,)) is True

    b = BinarySensor(111, "B 3", on=0b11, off=0b10, bitmask=0b11)
    assert b.reg_to_value((0b10,)) is False
    assert b.reg_to_value((0b1110,)) is False
    assert b.reg_to_value((0b11,)) is True
    assert b.reg_to_value((0b1111,)) is True
    assert b.reg_to_value((0b00,)) is False
    assert b.reg_to_value((0b01,)) is False


def test_sen() -> None:
    """Tests."""
    s = Sensor(0, "S 1")
    a = [s]
    assert a[0] == s
    assert s.id == "s_1"

    # Test __hash__
    s2 = Sensor(0, "S 2")
    ss = {s, s}
    assert len(ss) == 1
    ss = {s, s2}
    assert len(ss) == 2

    # Test eq
    s22 = Sensor(0, "S 2")
    assert s != s2
    assert s22 == s2
    with pytest.raises(TypeError):
        assert s == 0


def test_sensor_hash() -> None:
    """Tests."""
    ss = {Sensor(0, "S 1"), Sensor(0, "S 1")}
    assert len(ss) == 1
    ss = {Sensor(0, "S 1"), Sensor(0, "S 2")}
    assert len(ss) == 2

    s = Sensor(0, "S 1")
    m = MathSensor((0, 1), "math1", factors=(1, 1))
    b = BinarySensor((0,), "b1")
    ss = {s, m, b}
    assert len(ss) == 3


def test_sensor16() -> None:
    """Tests."""
    with pytest.raises(AssertionError):
        Sensor16((1,), "nope")
    s = Sensor16((1, 2), "power", "W", -1)
    assert s.reg_to_value((0xFFFF, 0x0)) == -1
    # since val transitioned the +/- boundary, interpret 10 values as 16-bit only
    for i in range(9):
        assert s.reg_to_value((i, 0x1)) == i
    # Then back to 32-bit
    assert s.reg_to_value((0x0, 0x1)) == 0x10000
    # once we have a 0, then it's 16-bit again
    assert s.reg_to_value((0xFFFF, 0x0)) == -1
    assert s.reg_to_value((0xFFFF, 0xFFFF)) == -1
    for i in range(8):
        assert s.reg_to_value((i, 0x1)) == i
    assert s.reg_to_value((0xFFFF, 0x1)) == 0x1FFFF

    # Test neg to po transition on reg[0]
    for _ in range(10):
        assert s.reg_to_value((0xFFFF, 0xFFFF)) == -1
    assert s.reg_to_value((0x0, 0xFFFF)) == 0


def test_group() -> None:
    """Tests."""
    sen = [
        Sensor(10, "10"),
        Sensor(11, "11"),
        Sensor(12, "12"),
        Sensor(20, "20"),
    ]
    g = list(group_sensors(sen))
    assert g == [[10, 11, 12], [20]]

    assert len(list(group_sensors(None))) == 0  # type: ignore[arg-type]


def test_group_max_size() -> None:
    """Tests."""
    sen = [
        Sensor(10, "10"),
        Sensor(11, "11"),
        Sensor(12, "12"),
        Sensor(13, "13"),
        Sensor(14, "14"),
        Sensor(15, "15"),
        Sensor(16, "16"),
    ]
    g = list(group_sensors(sen, max_group_size=3))
    assert g == [[10, 11, 12], [13, 14, 15], [16]]

    sen = [
        Sensor(10, "10"),
        Sensor(111, "11"),
        Sensor(112, "12"),
        Sensor(13, "13"),
        Sensor(14, "14"),
        Sensor(15, "15"),
        Sensor(16, "16"),
    ]
    g = list(group_sensors(sen, max_group_size=3))
    assert g == [[10], [13, 14, 15], [16], [111, 112]]


def test_all_groups() -> None:
    """Tests."""
    s = [SENSORS.all[s] for s in SENSORS.all]
    for i in range(2, 6):
        _LOGGER.warning("waste with %d gap: %s", i, waste(group_sensors(s, i)))

    grp = group_sensors(s)

    grplen = [len(i) for i in grp]

    assert grplen[:1] == [7]


def waste(groups: Iterable[list[int]]) -> Sequence[int]:
    """Calculate amount of unused registers in this grouping."""
    return [sum(b - a for a, b in pairwise(g)) for g in groups]


def test_ids() -> None:
    """Tests."""
    for name, sen in SENSORS.all.items():
        assert name == sen.id

        try:
            if sen.factor and sen.factor < 0 and len(sen.address) > 1:
                raise AssertionError("only single signed supported")
        except TypeError:
            _LOGGER.error("Sensor %s, factor=%s", name, sen.factor)
            raise

        if sen.id in SENSORS.deprecated:
            continue
        assert sen.unit != AMPS or sen.name.endswith(" current")
        assert sen.unit != WATT or sen.name.endswith(" power")
        assert sen.unit != VOLT or sen.name.endswith(" voltage")
        assert sen.unit != CELSIUS or sen.name.endswith(" temperature")


def test_other_sensors() -> None:
    """Tests."""
    s: Sensor = TempSensor(1, "", "", 0.1)
    assert s.reg_to_value((1000,)) == 0

    s = SDStatusSensor(1, "", "")
    assert s.reg_to_value((1000,)) == "fault"
    assert s.reg_to_value((1,)) == "unknown 1"

    s = InverterStateSensor(1, "", "")
    assert s.reg_to_value((2,)) == "ok"
    assert s.reg_to_value((6,)) == "unknown 6"


def test_math() -> None:
    """Tests."""
    s = MathSensor((1, 2), "", "", factors=(1, -1))
    assert s.reg_to_value((1000, 800)) == 200

    with pytest.raises(AssertionError):
        MathSensor((0, 1), "", "", factors=(1,))

    with pytest.raises(AssertionError):
        MathSensor((0, 1), "", "", factors="aaa")

    with pytest.raises(TypeError):
        MathSensor((0, 1), "", "")

    assert s.reg_to_value((200, 800)) == -600
    s.no_negative = True
    assert s.reg_to_value((200, 800)) == 0
    s.no_negative = False
    s.absolute = True
    assert s.reg_to_value((200, 800)) == 600
    s = MathSensor((1, 2), "", "", factors=(1, -1), absolute=True)
    assert s.reg_to_value((200, 800)) == 600


def test_update_func() -> None:
    """Tests."""
    s = SerialSensor(1, "", "")
    regs = (0x4148, 0x3738)
    assert s.reg_to_value(regs) == "AH78"


# def test_update_float(caplog) -> None:
#     s = TempSensor(60, "two", factors=0.1)
#     rmap = register_map(60, [1001])
#     update_sensors([s], rmap)

#     assert s.value == 0.1

#     s.reg_value = (None,)
#     s.update_value()
#     assert "Could not decode" in caplog.text


def test_decode_fault() -> None:
    """Tests."""
    s = FaultSensor(1, "", "")
    regs = (0x01, 0x0, 0x0, 0x0)
    assert s.reg_to_value(regs) == "F01"
    regs = (0x02, 0x0, 0x0, 0x0)
    assert s.reg_to_value(regs) == "F02"
    regs = (0x80, 0x0, 0x0, 0x0)
    assert s.reg_to_value(regs) == "F08"

    regs = (0x0, 0x8000, 0x0, 0x0)
    assert s.reg_to_value(regs) == "F32"
    regs = (0x0, 0x0, 0x1, 0x0)
    assert s.reg_to_value(regs) == "F33"
