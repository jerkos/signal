from unittest.mock import Mock

from assertpy import assert_that
from src.signal import HooksSet, Signal

synchronizer_hooks = HooksSet(
    "synchronizer", signals=[Signal("before"), Signal("current"), Signal("after")]
)


@synchronizer_hooks.register_cls
class TestHooks:
    @synchronizer_hooks.signal_by_name("before").cb
    def on_before(self):
        print("on before")

    @synchronizer_hooks.signal_by_name("current").cb
    def on_current(self):
        print("on current")

    @synchronizer_hooks.signal_by_name("after").cb
    def on_after(self):
        print("on after")


fire_tata = Signal("fire_tata")


@fire_tata.register_cls
class Toto:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    @fire_tata.cb
    def tata(self):
        self.x += 1
        print("hello", self.x)


@fire_tata.register_cls
class Titi:
    @fire_tata.cb
    def tata(self):
        print("hola")


class Tata:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def tata(self):
        print("tata")


def a_cb():
    print("a")


def test_same_name_same_signal():
    s = Signal("My signal")
    s2 = Signal("My signal")
    assert_that(s).is_same_as(s2)


def test_call_simple_function():
    s = Signal("My signal")
    m = Mock(a_cb)
    s.register_fn(m)
    s.fire()
    m.assert_called_once()

    s2 = Signal("My signal 2")
    m2 = Mock(a_cb)
    s2.fire()
    m2.assert_not_called()


def test_class():
    toto = Toto(1, 2)
    fire_tata.fire()
    assert_that(toto.x).is_equal_to(2)

    tata = Tata(1, 2, 3)
    tata_tata_mock = Mock(tata.tata)
    tata.tata = tata_tata_mock
    fire_tata.fire()
    tata_tata_mock.assert_not_called()


def test_no_decorator():
    tata = Tata(1, 2, 3)
    tata_tata_mock = Mock(tata.tata)
    tata.tata = tata_tata_mock
    fire_tata.register_subscriber(tata, tata.tata)
    fire_tata.fire()
    tata_tata_mock.assert_called_once()


def test_receiver():
    toto = Toto(1, 2)
    toto2 = Toto(2, 4)
    assert_that(toto).is_not_same_as(toto2)
    fire_tata.fire(receiver=toto)
    assert_that(toto.x).is_equal_to(2)
    assert_that(toto2.x).is_equal_to(2)
