import asyncio
import dataclasses
import logging
import typing as t
from typing import Any, Callable

if t.TYPE_CHECKING:
    from src.base_signal import Signal  # pragma: no cover

AnyFunc = Callable[..., Any]


def exec_sync(fn: AnyFunc, *args: Any, **kwargs: Any) -> Any:
    """execute a function synchronously"""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logging.exception(e)
        return None


async def exec_async(fn: AnyFunc, *args: Any, **kwargs: Any) -> Any:
    """execute a function asynchronously"""
    if not asyncio.iscoroutinefunction(fn):
        logging.info("Fn is not coroutine, running in a thread")
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as e:
            logging.exception(e)
            return None
    else:
        coroutine = fn(*args, **kwargs)
        try:
            return await coroutine
        except Exception as e:
            logging.exception(e)
            return None


def is_bound(fn: AnyFunc) -> bool:
    """check if a function is bound to a class"""
    return hasattr(fn, "__self__")


def is_bound_to(fn: AnyFunc, obj: Any) -> bool:
    """check if a function is bound to a specific object"""
    # noinspection PyUnresolvedReferences
    return is_bound(fn) and fn.__self__ is obj


T = t.TypeVar("T", bound=t.Type[Any])


def singleton(cls: T) -> Callable[..., T]:
    """singleton decorator"""
    instance = None

    def wrapper(*args: Any, **kwargs: Any) -> T:
        nonlocal instance
        if instance is None:
            instance = cls(*args, **kwargs)
        return instance

    return wrapper


@dataclasses.dataclass
class FnInformation:
    fn: AnyFunc
    depends_on: set[str] = dataclasses.field(default_factory=set)


def get_registered_methods(
    obj: Any, signal: "Signal"
) -> t.Iterator[tuple[str, FnInformation]]:
    """get all registered methods of an object for a specific signal"""
    for m in dir(obj):
        try:
            method = getattr(obj, m)
        except AttributeError:
            # getattr raises an AttributeError when not default provided
            continue
        is_registered_method = hasattr(method, f"__{signal.name}_event__")
        if method is None or not is_registered_method:
            continue
        events = getattr(method, f"__{signal.name}_event__")
        depends_on = getattr(method, f"__{signal.name}_depends_on__")
        for event in events:
            yield event, FnInformation(method, depends_on)
