import asyncio
import logging
from typing import Any, Callable

AnyFunc = Callable[[Any], Any]


def _exec_sync(fn: AnyFunc, *args, **kwargs) -> Any:
    """execute a function synchronously"""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logging.exception(e)
        return None


async def _exec_async(
    fn: AnyFunc,
    *args,
    **kwargs,
) -> Any:
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
