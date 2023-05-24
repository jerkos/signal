import asyncio
import collections
import itertools
import weakref
from typing import Any, Generic, Iterable, Mapping, Type, TypeVar, final

from src.utils import AnyFunc, _exec_async, _exec_sync, is_bound, is_bound_to

T = TypeVar("T")


class Reactive(Generic[T]):
    def __init__(self, signal: "Signal", data: T | None = None, default: T = None):
        self._data = data or default
        self._signal = signal

    def get(self) -> T:
        return self._data

    def set(self, data: T) -> None:
        if isinstance(data, Mapping):
            self._data = {**self._data, **data}
        else:
            self._data = data
        self._signal.fire()


class _RegisterClass:
    def __init__(self, signal: "Signal"):
        self._signal = signal

    def register(self, klass: Type):
        if not isinstance(klass, type):
            raise TypeError("Can only register classes")

        old_new = klass.__new__

        # noinspection PyArgumentList
        def new(klazz, *args: Any, **kwargs: Any):
            try:
                obj = old_new(klazz, *args, **kwargs)
            except TypeError:
                obj = old_new(klazz)

            for m in dir(obj):
                value = getattr(obj, m)
                is_registered_method = hasattr(
                    value, f"__{self._signal.name}_registered__"
                )
                if value is not None and is_registered_method:
                    tag = getattr(value, f"__{self._signal.name}_tag__", None)
                    self._signal.cb_fn_by_tag[tag].append(value)
            self._signal.subscribers.append(obj)
            return obj

        klass.__new__ = new

        return klass

    def cb(self, tag: str | None = None) -> AnyFunc:
        def wrapper(fn: AnyFunc) -> AnyFunc:
            setattr(fn, f"__{self._signal.name}_registered__", True)
            setattr(fn, f"__{self._signal.name}_tag__", tag)
            return fn

        return wrapper


class _RegisterFn:
    def __init__(self, signal: "Signal"):
        self._signal = signal

    def register(self, tag: str | None = None) -> AnyFunc:
        def wrapper(fn: AnyFunc) -> AnyFunc:
            self._signal.cb_fn_by_tag[tag].append(fn)
            return fn

        return wrapper


class _Fire:
    def __init__(self, signal: "Signal"):
        self._signal = signal
        self.receivers = []
        self.tags = []

    def for_receivers(self, receivers: Iterable[Any]):
        self.receivers = receivers
        return self

    def for_receiver(self, receiver: Any):
        self.receivers = [receiver]
        return self

    def for_tags(self, tags: Iterable[str]):
        self.tags = tags
        return self

    def for_tag(self, tag: str):
        self.tags = [tag]
        return self

    def _find_fn(self) -> list[AnyFunc]:
        if not self.receivers and not self.tags:
            return itertools.chain.from_iterable(self._signal.cb_fn_by_tag.values())

        tags = self.tags if self.tags else [None]
        print(self._signal.cb_fn_by_tag.items(), tags)
        all_fns = []
        for tag, fns in self._signal.cb_fn_by_tag.items():
            if tag not in tags:
                continue
            for receiver in self.receivers or self._signal.subscribers:
                for fn in fns:
                    if is_bound_to(fn, receiver):
                        all_fns.append(fn)

        # no fn found, return empty list
        return all_fns

    def fire(self, *args, **kwargs):
        return [_exec_sync(fn, *args, **kwargs) for fn in self._find_fn()]

    def fire_in_bg(self, *args, **kwargs) -> list[asyncio.Task[Any]]:
        return [
            asyncio.create_task(_exec_async(fn, *args, **kwargs))
            for fn in self._find_fn()
        ]

    async def fire_async(self, *args: Any, **kwargs: Any) -> list[Any]:
        return await asyncio.gather(
            *[_exec_async(fn, *args, **kwargs) for fn in self._find_fn()]
        )


@final
class Signal:
    """
    A signal is a way to send a message to multiple receivers.
    """

    signal_by_name: dict[str, "Signal"] = weakref.WeakValueDictionary()
    cls: _RegisterClass | None = None
    fn: _RegisterFn | None = None

    def __new__(cls, name: str):
        """create a new signal or return an existing one"""
        if name in cls.signal_by_name:
            return cls.signal_by_name[name]
        obj = super().__new__(cls)
        return obj

    def __init__(self, name: str):
        """create a new signal or return an existing one"""
        if name not in self.__class__.signal_by_name:
            # in a list to avoid non hashable types
            self.subscribers: list[Any] = []
            self.cb_fn_by_tag: collections.defaultdict[
                str | None, list[AnyFunc]
            ] = collections.defaultdict(list)
            self.name = name
            self.__class__.signal_by_name[name] = self
            self.__class__.cls = _RegisterClass(self)
            self.__class__.fn = _RegisterFn(self)

    def register(self, fn: AnyFunc, tag: str = None) -> None:
        """register a function to the signal"""
        if fn not in itertools.chain.from_iterable(self.cb_fn_by_tag.values()):
            self.cb_fn_by_tag[tag].append(fn)
        # noinspection PyUnresolvedReferences
        if is_bound(fn) and (obj := fn.__self__) not in self.subscribers:
            self.subscribers.append(obj)

    def unsubscribe(self, subscriber: Any) -> None:
        """unsubscribe"""
        try:
            self.subscribers.remove(subscriber)
        except ValueError:
            pass

    def firing_opts(self) -> _Fire:
        return _Fire(self)

    def fire(self, *args: Any, **kwargs: Any) -> list[Any]:
        """fire an event synchronously"""
        return _Fire(self).fire(*args, **kwargs)

    async def fire_async(
        self, *args: Any, **kwargs: Any
    ) -> list[asyncio.Task[Any]] | list[Any]:
        """fire an event asynchronously"""
        return await _Fire(self).fire_async(*args, **kwargs)

    def fire_in_bg(self, *args: Any, **kwargs: Any) -> list[asyncio.Task[Any]]:
        return _Fire(self).fire_in_bg(*args, **kwargs)

    def reactive(self, data: Any | None = None, default: Any | None = None) -> Reactive:
        return Reactive(self, data, default)
