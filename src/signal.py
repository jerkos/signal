import collections
import enum
import itertools
import logging
import uuid
import weakref
from typing import (
    Any,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Protocol,
    Type,
    TypeVar,
    final,
)

from src.utils import (  # exec_async,
    AnyFunc,
    FnInformation,
    exec_sync,
    get_registered_methods,
    is_bound,
    is_bound_to,
)

TReactive = TypeVar("TReactive")


class Reactive(Generic[TReactive]):
    """A reactive object that can be used to trigger events when its value changes"""

    def __init__(
        self,
        signal: "Signal",
        data: TReactive | None = None,
        default: TReactive | None = None,
    ):
        self._data = data or default
        self._signal = signal

    def get(self) -> TReactive:
        """
        Get the value of the reactive object
        Returns:

        """
        return self._data

    def set(self, data: TReactive) -> None:
        """
        Set the value of the reactive object
        firing the signal if the value changes
        Args:
            data:

        Returns:

        """
        if isinstance(data, Mapping):
            self._data = {**self._data, **data}
        else:
            self._data = data
        self._signal.fire()


class _Register:
    """
    Provides utilities to decorate a class with methods that can be registered to a signal
    """

    def __init__(self, signal: "Signal"):
        self._signal = signal

    def _setattr(
        self, fn: AnyFunc, event: str | None = None, depends_on: list[str] | None = None
    ):
        """Set attribute on a class method"""
        events = getattr(fn, f"__{self._signal.name}_event__", set())
        events.add(event)
        setattr(fn, f"__{self._signal.name}_event__", events)
        setattr(fn, f"__{self._signal.name}_depends_on__", depends_on or [])
        return fn

    def cls(self, klass: Type[Any]) -> Type[Any]:
        """
        Decorator to register all methods of a class to a signal
        Args:
            klass: class to register

        Returns:
            the class with all methods registered
        """
        if not isinstance(klass, type):
            raise TypeError("Can only register classes")

        old_new = klass.__new__

        # noinspection PyArgumentList
        def new(klazz, *args: Any, **kwargs: Any):
            try:
                obj = old_new(klazz, *args, **kwargs)
            except TypeError:
                obj = old_new(klazz)

            for event, value in get_registered_methods(obj, self._signal):
                self._signal.fn_by_event[event].append(value)

            return obj

        klass.__new__ = new

        # registering only event dependencies
        for cls_event, cls_value in get_registered_methods(klass, self._signal):
            self._signal.dependencies_by_event[cls_event].update(cls_value.depends_on)

        return klass

    def on_event(self, event: str | None = None, depends_on: list[str] | None = None):
        """
        Decorator to register a method to a signal
        Args:
            event:
            depends_on:

        Returns:

        """

        def wrapper(fn: AnyFunc) -> AnyFunc:
            return self._setattr(fn, event, depends_on)

        return wrapper

    def cls_cb(self, fn: AnyFunc) -> AnyFunc:
        return self._setattr(fn)

    def fn(
        self, fn_or_event: str | AnyFunc = None, depends_on: list[str] | None = None
    ) -> AnyFunc:
        def wrapper(fn: AnyFunc) -> AnyFunc:
            self._signal.fn_by_event[fn_or_event].append(
                FnInformation(fn, depends_on=depends_on)
            )
            return fn

        if callable(fn_or_event):
            return wrapper(fn_or_event)
        return wrapper


class _Resolver:
    def __init__(self, signal: "Signal"):
        self._signal = signal

    def resolve(
        self,
        target_event: str,  # always a string
        _path: list[str] | None = None,
        _results: list[list[str]] | None = None,
    ):
        path = _path or []

        # appending the current event to the path
        path.append(target_event)

        # getting the information about event dependencies
        event_dependencies = self._signal.dependencies_by_event[target_event]
        if not event_dependencies:
            _results.append(list(reversed(path)))
        else:
            for dependency in event_dependencies:
                new_path = path[:]
                self.resolve(dependency, new_path, _results)


class _Fire(Protocol):
    _signal: "Signal"
    _events: list[str] | None = None
    _receivers: list[Any] | None = None

    def _iter_receivers(self, fns: list[FnInformation]) -> Iterable[FnInformation]:
        for receiver in self._receivers:
            for fn_information in fns:
                if is_bound_to(fn_information.fn, receiver):
                    yield fn_information

    def _find_fn_to_fire(self) -> Iterable[FnInformation]:
        if not self._receivers and not self._events:
            yield from itertools.chain.from_iterable(self._signal.fn_by_event.values())
            return

        events = self._events if self._events else [None]
        # we are working on a copy of the dict because we are potentially going to modify it
        for event, fns in self._signal.fn_by_event.copy().items():
            if event not in events:
                continue
            if not self._receivers:
                yield from fns
                return

            yield from self._iter_receivers(fns)


class _FireSync(_Fire):
    """
    A class that can be used to fire a signal synchronously
    """

    def __init__(
        self,
        signal: "Signal",
        *,
        events: list[str] | None = None,
        chain: bool = False,
        path_type: "Optional[PathType]" = None,
        receivers: list[Any] | None = None,
        resolver: _Resolver | None = None,
    ):
        self._signal = signal
        self._events = events
        self._receivers = receivers
        self._resolver = resolver
        self._chain = chain
        self._path_type = path_type or PathType.SHORTEST

    def _fire_raw(self, *args: Any, **kwargs: Any):
        print(list(self._find_fn_to_fire()))
        return [exec_sync(fn.fn, *args, **kwargs) for fn in self._find_fn_to_fire()]

    def _fire(self, *args, **kwargs):
        if not self._events:
            return self._fire_raw(*args, **kwargs)

        for event in self._events:
            path_for_event: list[list[str]] = []
            self._resolver.resolve(event, None, path_for_event)
            if not path_for_event:
                continue

            chosen_path = sorted(
                path_for_event, key=len, reverse=self._path_type == PathType.LONGEST
            )[0]
            result = None
            fn_args, fn_kwargs = args, kwargs
            for chosen_event in chosen_path:
                result = _FireSync(
                    self._signal, events=[chosen_event], resolver=self._resolver
                )._fire_raw(*fn_args, **fn_kwargs)
                if self._chain:
                    fn_args, fn_kwargs = result, {}
            return result

    def __call__(self, *args: Any, **kwargs: Any):
        return self._fire(*args, **kwargs)


class PathType(enum.StrEnum):
    SHORTEST = "shortest"
    LONGEST = "longest"


FnInformationByEvent = collections.defaultdict[str | None, list[FnInformation | None]]


@final
class Signal:
    """
    A signal is a way to send a message to multiple receivers.
    """

    signal_by_name: dict[str, "Signal"] = weakref.WeakValueDictionary()
    fire_sync_cls = _FireSync
    # fire_async_cls = _FireAsync

    def __new__(cls, name: str | None = None):
        """create a new signal or return an existing one"""
        if name is not None and name in cls.signal_by_name:
            return cls.signal_by_name[name]
        obj = super().__new__(cls)
        return obj

    def __init__(self, name: str | None = None):
        """create a new signal or return an existing one"""
        if name is None or name not in self.__class__.signal_by_name:
            # a dict of list of functions or cb by event
            # to call when the signal is fired
            self.fn_by_event: FnInformationByEvent = collections.defaultdict(list)

            # a dict of dependencies by event to compute
            # sequential signal firing
            self.dependencies_by_event: collections.defaultdict[
                str, set[str]
            ] = collections.defaultdict(set)

            # given name or a generated one
            self.name = name or str(uuid.uuid4())

            # registering signal in the class attribute
            self.__class__.signal_by_name[self.name] = self

            # a wire object providing decorator to register functions
            self.wire = _Register(self)

    def register(
        self,
        fn: AnyFunc,
        *,
        event: str | None = None,
        depends_on: set[str] | None = None,
    ) -> None:
        """register a function to the signal"""
        if fn not in self.fn_by_event[event]:
            self.fn_by_event[event].append(FnInformation(fn, depends_on))
        else:
            logging.info("fn already registered for this event: %s, %s", fn, event)
        if is_bound(fn):
            # we put special tags on the function of class
            # the class methods may not have been decorated
            # and must show up during the resolution
            if event is not None:
                # noinspection PyUnresolvedReferences
                self.wire.on_event(event)(fn.__func__)
            else:
                # noinspection PyUnresolvedReferences
                self.wire.cls_cb(fn.__func__)

    def fire(
        self,
        *,
        events: list[str] | None = None,
        receivers: list[Any] | None = None,
    ) -> _FireSync | list[Any]:
        """fire an event synchronously"""
        return self.fire_sync_cls(
            self, events=events, receivers=receivers, resolver=_Resolver(self)
        )

    def get_event_path(
        self, event: str, path_type: PathType | None = None
    ) -> list[list[str]] | list[str]:
        """get the path of events to fire for a given event"""
        path_for_event: list[list[str]] = []
        _Resolver(self).resolve(event, None, path_for_event)
        if not path_type:
            return path_for_event
        return sorted(path_for_event, key=len, reverse=path_type == PathType.LONGEST)[0]

    def reactive(self, data: Any | None = None, default: Any | None = None) -> Reactive:
        return Reactive(self, data, default)
