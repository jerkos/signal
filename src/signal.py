import asyncio
import collections
import weakref
import logging
from typing import final, Callable, Any, Type, Iterator

AnyFunc = Callable[[Any], Any]


def _exec_sync(fn: AnyFunc, *args, **kwargs) -> Any:
    """execute a function synchronously"""
    print(fn, *args, **kwargs)
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logging.exception(e)


async def _exec_async(
    fn: AnyFunc,
    background: bool = False,
    loop: asyncio.BaseEventLoop = None,
    *args,
    **kwargs,
) -> Any:
    """execute a function asynchronously"""
    while hasattr(fn, "__func__"):
        # noinspection PyUnresolvedReferences
        fn = fn.__func__
    if not asyncio.iscoroutinefunction(fn):
        logging.info("Fn is not coroutine, running in a thread")
        try:
            if background:
                asyncio.create_task(asyncio.to_thread(fn, *args, **kwargs))
            else:
                await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as e:
            logging.exception(e)
    else:
        coroutine = fn(*args, **kwargs)
        try:
            if loop is not None:
                asyncio.run_coroutine_threadsafe(coroutine, loop=loop)
            if background:
                asyncio.create_task(coroutine)
        except Exception as e:
            logging.exception(e)


@final
class Signal:
    """
    A signal is a way to send a message to multiple receivers.
    """

    signal_by_name: dict[str, "Signal"] = weakref.WeakValueDictionary()

    def __new__(cls, name: str):
        """create a new signal or return an existing one"""
        if name in cls.signal_by_name:
            return cls.signal_by_name[name]
        obj = super().__new__(cls)
        return obj

    def __init__(self, name: str):
        """create a new signal or return an existing one"""
        if name not in self.__class__.signal_by_name:
            self.subscribers: list[Any] = []
            self.fn_by_cls: collections.defaultdict[
                Type[Any], list[AnyFunc]
            ] = collections.defaultdict(list)
            self.orphan_fn: list[AnyFunc] = []
            self.name = name
            self.__class__.signal_by_name[name] = self

    def _register_fn(self, cls: Type[Any]) -> Type[Any]:
        """
        register all functions decorated with @cb
        Args:
            cls:

        Returns:

        """
        for m in dir(cls):
            value = getattr(cls, m)
            if value is not None and hasattr(value, f"__{self.name}_registered__"):
                self.fn_by_cls[cls].append(value)
        return cls

    def _find_fn(
        self, receiver: Any | None = None
    ) -> Iterator[tuple[AnyFunc, Any]] | None:
        """
        find a function to call
        Args:
            receiver:

        Returns:

        """
        subscribers = (
            self.subscribers
            if receiver is None
            else [s for s in self.subscribers if s is receiver]
        )
        for subscriber in subscribers:
            fn_to_call = self.fn_by_cls[subscriber.__class__]
            for fn in fn_to_call:
                yield fn, subscriber
        return None

    def cb(self, fn: AnyFunc) -> AnyFunc:
        """decorator for function"""
        setattr(fn, f"__{self.name}_registered__", True)
        return fn

    def register_cls(self, cls: Type[Any] = None) -> Type[Any]:
        """register class decorator"""

        # noinspection PyUnusedLocal
        def new(klass: Type[Any], *args: Any, **kwargs: Any):
            # noinspection PyTypeChecker
            obj = object.__new__(klass)
            self.subscribers.append(obj)
            return obj

        cls.__new__ = new

        return self._register_fn(cls)

    def fire(self, receiver: Any | None = None, *args, **kwargs) -> Any:
        """fire an event synchronously"""
        for fn in self.orphan_fn:
            _exec_sync(fn, *args, **kwargs)

        for fn, subscriber in self._find_fn(receiver):
            is_bound = hasattr(fn, "__self__")
            if is_bound:
                _exec_sync(fn, *args, **kwargs)
            else:
                _exec_sync(fn, subscriber, *args, **kwargs)

    async def fire_async(
        self,
        receiver: Any | None = None,
        background: bool = False,
        loop: asyncio.BaseEventLoop = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """fire an event"""
        for fn, subscriber in self._find_fn(receiver):
            is_bound = hasattr(fn, "__self__")
            if is_bound:
                await _exec_async(fn, background, loop, *args, **kwargs)
            else:
                await _exec_async(fn, background, loop, subscriber, *args, **kwargs)

    def unsubscribe(self, subscriber: Any) -> None:
        """unsubscribe"""
        try:
            self.subscribers.remove(subscriber)
        except ValueError:
            pass

    def register_subscriber(self, subscriber: Any, callable_: AnyFunc):
        if subscriber not in self.subscribers:
            self.subscribers.append(subscriber)
            self.fn_by_cls[subscriber.__class__].append(callable_)

    def register_fn(self, fn: AnyFunc):
        self.orphan_fn.append(fn)


class HooksSet:
    def __init__(self, name: str, signals: list[Signal]):
        self.name = name
        self.signals = signals

    def signal_by_name(self, name) -> Signal | None:
        return next(s for s in self.signals if s.name == name)

    def register_cls(self, cls: Type[Any]) -> Type[Any]:
        klass = cls
        for s in self.signals:
            # noinspection PyProtectedMember
            s._register_fn(cls)

        # noinspection PyUnusedLocal
        def new(a_class, *args, **kwargs):
            obj = object.__new__(a_class)
            for signal in self.signals:
                signal.subscribers.append(obj)
            return obj

        cls.__new__ = new

        return klass

    def chain(self, *args: Any, **kwargs: Any):
        curr = args, kwargs
        for s in self.signals:
            s.fire(curr)

    def fire(self, *args: Any, **kwargs: Any):
        for s in self.signals:
            s.fire(*args, **kwargs)
