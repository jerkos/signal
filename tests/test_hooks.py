import asyncio
import functools
import time
from unittest.mock import Mock

import pytest
from assertpy import assert_that

from src.signal import Signal

fire_titi = Signal("fire_titi")


@fire_titi.cls.register
class Toto:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    @fire_titi.cls.cb()
    def tata(self):
        self.x += 1
        print("hello", self.x)


fire_tata = Signal("fire_tata")


@fire_tata.cls.register
class Tata:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    @fire_tata.cls.cb(tag="tata")
    def increase_x(self):
        print("tata")
        self.x += 1

    @fire_tata.cls.cb(tag="titi")
    def increase_y(self):
        print("titi")
        self.y += 1


def a_cb():
    print("a")


fn_signal = Signal("fn_signal")


@fn_signal.fn.register()
def b_cb():
    print("b")


def test_same_name_same_signal():
    s = Signal("My signal")
    s2 = Signal("My signal")
    assert_that(s).is_same_as(s2)


def test_call_simple_function():
    s = Signal("My signal")
    m = Mock(a_cb)
    s.register(m)
    s.fire()
    m.assert_called_once()

    s2 = Signal("My signal 2")
    m2 = Mock(a_cb)
    s2.fire()
    m2.assert_not_called()


def test_class():
    toto = Toto(1, 2)
    fire_titi.fire()
    assert_that(toto.x).is_equal_to(2)

    tata = Tata(1, 2, 3)
    tata_tata_mock = Mock(tata.increase_x)
    tata.increase_x = tata_tata_mock
    fire_titi.fire()
    tata_tata_mock.assert_not_called()


def test_no_decorator():
    tata = Tata(1, 2, 3)
    tata_tata_mock = Mock(tata.increase_x)
    tata.increase_x = tata_tata_mock
    fire_titi.register(tata.increase_x)
    fire_titi.fire()
    tata_tata_mock.assert_called_once()


def test_receiver():
    toto = Toto(1, 2)
    toto2 = Toto(2, 4)
    assert_that(toto).is_not_same_as(toto2)
    fire_titi.firing_opts().for_receivers([toto]).fire()
    assert_that(toto.x).is_equal_to(2)
    assert_that(toto2.x).is_equal_to(2)


@pytest.mark.asyncio
async def test_async_cb():
    async def a():
        await asyncio.sleep(0.1)
        print("a")

    s = Signal("async signal")
    s.register(a)
    await s.fire_async()

    def b():
        time.sleep(0.1)
        print("b")

    s.register(b)
    await s.fire_async()


def test_partial_func():
    def a(x, y):
        return x + y

    s = Signal("partial signal")
    s.register(functools.partial(a, x=1))
    assert_that(s.fire(y=1)).contains(2)


def test_tag():
    tata = Tata(1, 2, 3)
    fire_tata.firing_opts().for_tag("tata").fire()
    assert_that(tata.x).is_equal_to(2)
    assert_that(tata.y).is_equal_to(2)


def test_reactive():
    s = Signal("python_component")

    @s.cls.register
    class PythonComponent2:
        def __init__(self):
            self.state = s.reactive(
                {
                    "name": "python_component",
                    "description": "Python component",
                }
            )

        def on_click(self):
            print("on click")
            self.state.set({"name": "new name"})

        @s.cls.cb()
        def render(self):
            print(
                f"""
                <div>
                 <h1>{self.state.get()['name']}</h1>
                 <p>{self.state.get()['description']}</p>
                 <button onclick={self.on_click}>Change name</button>
                </div>
                """
            )

    p = PythonComponent2()
    p.render()
    p.on_click()
    print(s.subscribers)
