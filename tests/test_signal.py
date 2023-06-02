import asyncio
import functools
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import Mock

import pytest
from assertpy import assert_that

from src.signal import Signal

fire_titi = Signal("fire_titi")


@fire_titi.wire.cls
class Toto:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    @fire_titi.wire.cls_cb
    def tata(self):
        self.x += 1
        print("hello", self.x)


fire_tata = Signal("fire_tata")


@fire_tata.wire.cls
class Tata:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    @fire_tata.wire.on_event("tata")
    def increase_x(self):
        print("tata")
        self.x += 1

    @fire_tata.wire.on_event("titi")
    def increase_y(self):
        print("titi")
        self.y += 1


def a_cb():
    print("a")


fn_signal = Signal("fn_signal")


@fn_signal.wire.fn
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
    s.fire()()
    m.assert_called_once()

    s2 = Signal("My signal 2")
    m2 = Mock(a_cb)
    s2.fire()()
    m2.assert_not_called()


def test_class():
    toto = Toto(1, 2)
    fire_titi.fire()()
    assert_that(toto.x).is_equal_to(2)

    tata = Tata(1, 2, 3)
    fire_titi.fire()()
    assert_that(tata.x).is_equal_to(1)


def test_no_decorator():
    tata = Tata(1, 2, 3)
    fire_tata.register(tata.increase_x)
    fire_tata.fire(events=["tata"])()
    assert_that(tata.x).is_equal_to(2)


def test_receiver():
    toto = Toto(1, 2)
    toto2 = Toto(2, 4)
    assert_that(toto).is_not_same_as(toto2)
    fire_titi.fire(receivers=[toto])()
    assert_that(toto.x).is_equal_to(2)
    assert_that(toto2.x).is_equal_to(2)


@pytest.mark.asyncio
async def test_async_cb():
    async def a():
        await asyncio.sleep(0.1)
        print("a")

    s = Signal("async signal")
    s.register(a)
    await s.fire_async()()

    def b():
        time.sleep(0.1)
        print("b")

    s.register(b)
    await s.fire_async()()


def test_partial_func():
    def a(x, y):
        return x + y

    s = Signal("partial signal")
    s.register(functools.partial(a, x=1))
    assert_that(s.fire()(y=1)).contains(2)


def test_tag():
    tata = Tata(1, 2, 3)
    fire_tata.fire(events=["tata"])()
    assert_that(tata.x).is_equal_to(2)
    assert_that(tata.y).is_equal_to(2)


def test_reactive():
    s = Signal("python_component")

    @s.wire.cls
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

        @s.wire.cls_cb
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


def test_resolver():
    s = Signal()

    class Car:
        def __init__(self, wheel):
            self.wheel = wheel

    @s.wire.cls
    class Wheel:
        def __init__(self, tire):
            self.tire = tire

        @s.wire.on_event("Car", depends_on={"Wheel"})
        def car(self) -> "Car":
            return Car(self)

    @s.wire.cls
    class Tire:
        def __init__(self, kind):
            self.kind = kind

        @s.wire.on_event("Wheel")
        def wheel(self) -> "Wheel":
            return Wheel(self)

    Tire("Michelin")
    car = s.fire(events=["Car"])()
    print(car)
    # print("car: ", car, "wheel :", car.wheel, "tire :", car.wheel.tire)


def test_classic():
    on_start = Signal("on_start")
    on_end = Signal("on_end")

    class Test:
        def __init__(self, x):
            self.x = x

        def first_step(self):
            on_start.fire()()
            val = self.x + 10
            on_end.fire()(val)
            return val

    t = Test(1)

    @on_start.wire.fn
    def on_start_fn():
        print("on start")

    @on_end.wire.fn
    def on_end_fn(value):
        print(f"on end {value}")

    @on_end.wire.cls
    class Test2:
        @on_end.wire.cls_cb
        def finalize(self, value):
            print(f"finalize {value}")

    class Test3:
        def finalize(self, value):
            print(f"finalize the final {value}")

    Test2(2)

    # register another one
    t3 = Test3()
    on_end.register(t3.finalize)

    Test(1).first_step()


def test_not_name_signal():
    s = Signal()
    s2 = Signal()
    assert_that(s).is_not_same_as(s2)


mp_signal = Signal()


def mp_cb():
    return "mp_cb"


def in_mp(sig):
    return sig.fire()()


def test_mp_1():
    mp_signal.register(mp_cb)

    with multiprocessing.Pool(1) as p:
        r = p.apply_async(in_mp, args=(mp_signal,))
        p.close()
        p.join()
        assert_that(r.get()).is_equal_to(["mp_cb"])

    with ProcessPoolExecutor(max_workers=1) as executor:
        r = executor.submit(in_mp, mp_signal)
        assert_that(r.result()).is_equal_to(["mp_cb"])


mp_signal_2 = Signal()


def mp_cb_2():
    a = Tata(1, 2, 3)
    a.increase_x()
    print("called")
    return "mp_cb"


def in_mp_2(sig):
    return sig.fire()()


def test_mp_2():
    p = multiprocessing.Process(target=mp_cb_2)
    p.start()
    time.sleep(1)
    fire_tata.fire()()
    p.join()
