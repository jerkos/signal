import collections
import logging
import typing as t
import uuid
import weakref

from rustshed import Null, Option, Some

from src._firing import FireProtocol, PathType, _FireAsync, _FireSync
from src._register import _Register
from src._resolver import _Resolver
from src.queueing.backend import BackendCallable, BackendProtocol
from src.reactive import Reactive
from src.utils import AnyFunc, FnInformation, is_bound

FnInformationByEvent = collections.defaultdict[str | None, list[FnInformation]]


@t.final
class Signal:
    """
    A signal is a way to send a message to multiple receivers.
    """

    signal_by_name: weakref.WeakValueDictionary[
        str, "Signal"
    ] = weakref.WeakValueDictionary()

    def __new__(cls, name: str | None = None):
        """create a new signal or return an existing one"""
        if name is not None and name in cls.signal_by_name:
            return cls.signal_by_name[name]
        obj = super().__new__(cls)
        return obj

    def __init__(self, name: str | None = None):
        """create a new signal or return an existing one"""
        if name is None or name not in self.__class__.signal_by_name:
            self._backend: Option[BackendProtocol] = Null
            # fire cls
            self.fire_sync_cls: t.Type[FireProtocol] = _FireSync
            # fire async cls
            self.fire_async_cls: t.Type[FireProtocol] = _FireAsync

            # a dict of list of functions or cb by event
            # to call when the signal is fired
            self.fn_by_event: FnInformationByEvent = collections.defaultdict(list)

            # a dict of dependencies by event to compute
            # sequential signal firing
            self.dependencies_by_event: collections.defaultdict[
                str | None, set[str]
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
            self.fn_by_event[event].append(FnInformation(fn, depends_on or set()))
        else:
            logging.info("fn already registered for this event: %s, %s", fn, event)
        if is_bound(fn):
            # we put special tags on the function of class
            # the class methods may not have been decorated
            # and must show up during the resolution
            if event is not None:
                self.wire.cls_fn(event, depends_on)(fn.__func__)
            else:
                self.wire.cls_fn(fn.__func__)

    def fire(
        self,
        *,
        events: list[str | None] | None = None,
        receivers: list[t.Any] | None = None,
    ) -> FireProtocol:
        """fire an event synchronously"""
        return self.fire_sync_cls(self, events=events, receivers=receivers)

    def fire_with_backend(
        self,
        *,
        events: list[str | None] | None = None,
    ) -> BackendCallable:
        return self.backend.expect("No backend set").fire(events=events)

    def fire_async(
        self,
        *,
        events: list[str | None] | None = None,
        receivers: list[t.Any] | None = None,
    ) -> FireProtocol:
        """fire an event asynchronously"""
        return self.fire_async_cls(self, events=events, receivers=receivers)

    def get_event_path(
        self, event: str, path_type: PathType | None = None
    ) -> list[list[str | None]] | list[str | None]:
        """get the path of events to fire for a given event"""
        path_for_event: list[list[str | None]] = []
        _Resolver(self).resolve(event, path_for_event)
        if not path_type:
            return path_for_event
        return sorted(path_for_event, key=len, reverse=path_type == PathType.LONGEST)[0]

    def reactive(self, data: t.Any | None = None) -> Reactive:
        return Reactive(self, data)

    def set_fire_sync_cls(self, fire_sync_cls: t.Type[FireProtocol]) -> None:
        self.fire_sync_cls = fire_sync_cls

    def set_fire_async_cls(self, fire_async_cls: t.Type[FireProtocol]) -> None:
        self.fire_async_cls = fire_async_cls

    @property
    def backend(self) -> Option[BackendProtocol]:
        return self._backend

    @backend.setter
    def backend(self, backend: BackendProtocol) -> None:
        self._backend = Some(backend)
