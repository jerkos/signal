import abc
import asyncio
import enum
import itertools
import typing as t
from typing import Any

from src._resolver import _Resolver
from src.utils import FnInformation, exec_async, exec_sync, is_bound_to

if t.TYPE_CHECKING:
    from src.base_signal import Signal


class PathType(enum.StrEnum):
    SHORTEST = "shortest"
    LONGEST = "longest"


class FireProtocol(t.Protocol):
    _signal: "Signal"

    _events: list[str | None] | None
    _chain: bool
    _path_type: "PathType"

    _receivers: list[t.Any]

    _resolver: _Resolver

    def __init__(
        self,
        signal: "Signal",
        *,
        events: list[str | None] | None = None,
        chain: bool = False,
        path_type: "t.Optional[PathType]" = None,
        receivers: list[t.Any] | None = None,
        resolver: _Resolver | None = None,
    ):
        ...

    def _iter_receivers(self, fns: list[FnInformation]) -> t.Iterable[FnInformation]:
        for receiver in self._receivers:
            for fn_information in fns:
                if is_bound_to(fn_information.fn, receiver):
                    yield fn_information

    def _find_fn_to_fire(self) -> t.Iterable[FnInformation]:
        if not self._receivers and not self._events:
            yield from itertools.chain.from_iterable(self._signal.fn_by_event.values())
            return

        events = self._events if self._events else [None]
        # we are working on a copy of the dict because we are potentially going to
        # modify it
        for event, fns in self._signal.fn_by_event.copy().items():
            if event not in events:
                continue
            if not self._receivers:
                yield from fns
                return

            yield from self._iter_receivers(fns)

    def _get_chosen_path(self, event: str | None) -> list[str | None] | None:
        path_for_event: list[list[str | None]] = []
        self._resolver.resolve(event, path_for_event)
        if not path_for_event:
            return None
        return sorted(
            path_for_event, key=len, reverse=self._path_type == PathType.LONGEST
        )[0]

    def _fire(
        self, *args: t.Any, **kwargs: t.Any
    ) -> t.Generator[tuple[t.Iterable, t.Mapping, str | None], list[t.Any], None]:
        if not self._events:
            _ = yield args, kwargs, None
            yield (), {}, None  # make sure stop iteration is not raised
            return
        for event in self._events:
            chosen_path = self._get_chosen_path(event)
            if chosen_path is None:
                continue
            fn_args, fn_kwargs = args, kwargs
            for chosen_event in chosen_path:
                result = yield fn_args, fn_kwargs, chosen_event
                yield (), {}, None  # make sure stop iteration is not raised
                if self._chain:
                    fn_args, fn_kwargs = result, {}

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        ...


class _Fire(FireProtocol, abc.ABC):
    def __init__(
        self,
        signal: "Signal",
        *,
        events: list[str | None] | None = None,
        resolver: _Resolver | None = None,
        chain: bool = False,
        path_type: "t.Optional[PathType]" = None,
        receivers: list[t.Any] | None = None,
    ):
        self._signal = signal
        self._events = events
        self._receivers = receivers or []
        self._resolver = resolver or _Resolver(signal)
        self._chain = chain
        self._path_type = path_type or PathType.SHORTEST

    @abc.abstractmethod
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        ...


class _FireSync(_Fire):
    """
    A class that can be used to fire a signal synchronously
    """

    def _fire_raw(self, *args: t.Any, **kwargs: t.Any):
        return [exec_sync(fn.fn, *args, **kwargs) for fn in self._find_fn_to_fire()]

    def _fire(self, *args, **kwargs):
        result = None
        args_generator = super()._fire(*args, **kwargs)
        for fn_args, fn_kwargs, event in args_generator:
            result = _FireSync(
                self._signal,
                events=[event],
                receivers=self._receivers,
                resolver=self._resolver,
            )._fire_raw(*fn_args, **fn_kwargs)
            args_generator.send(result)
        else:
            return result

    def __call__(self, *args: t.Any, **kwargs: t.Any):
        return self._fire(*args, **kwargs)


class _FireAsync(_Fire):
    """
    A class that can be used to fire a signal synchronously
    """

    async def _fire_raw(self, *args: t.Any, **kwargs: t.Any):
        """
        Fires the signal without any event resolution
        Args:
            *args:
            **kwargs:

        Returns:

        """
        return await asyncio.gather(
            *[exec_async(fn.fn, *args, **kwargs) for fn in self._find_fn_to_fire()]
        )

    async def _fire(self, *args: t.Any, **kwargs: t.Any):
        result = None
        args_generator = super()._fire(*args, **kwargs)
        for fn_args, fn_kwargs, event in args_generator:
            result = await _FireAsync(
                self._signal,
                events=[event],
                receivers=self._receivers,
                resolver=self._resolver,
            )._fire_raw(*fn_args, **fn_kwargs)
            args_generator.send(result)
        else:
            return result

    async def __call__(self, *args: t.Any, **kwargs: t.Any):
        return await self._fire(*args, **kwargs)
