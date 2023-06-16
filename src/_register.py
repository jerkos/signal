import typing as t

from src.utils import AnyFunc, FnInformation, get_registered_methods

if t.TYPE_CHECKING:
    from src.base_signal import Signal


class _Register:
    """
    Provides utilities to decorate a class with methods that can be registered to
    a signal

    >>> @signal.wire.cls
    >>> class MyClass:
    >>>     def __init__(self, data):
    >>>         self.data = data
    >>>...
    >>>     @signal.wire.cls_fn
    >>>     def my_method(self):
    >>>         print(self.data)

    >>>     @signal.wire.cls_fn(on_event="my_event")
    >>>     def my_method(self):
    >>>         print(self.data)
    """

    def __init__(self, signal: "Signal"):
        self._signal = signal

    def _setattr(
        self, fn: AnyFunc, event: str | None = None, depends_on: set[str] | None = None
    ):
        """Set attribute on a class method"""

        # one function can be registered for several events
        events = getattr(fn, f"__{self._signal.name}_event__", set())
        events.add(event)
        setattr(fn, f"__{self._signal.name}_event__", events)
        setattr(fn, f"__{self._signal.name}_depends_on__", depends_on or set())
        return fn

    def cls(self, klass: t.Type[t.Any]) -> t.Type[t.Any]:
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

        def new(cls, *args: t.Any, **kwargs: t.Any):
            try:
                obj = old_new(cls, *args, **kwargs)
            except TypeError:
                obj = old_new(cls)  # type: ignore

            for event, value in get_registered_methods(obj, self._signal):
                self._signal.fn_by_event[event].append(value)

            return obj

        klass.__new__ = new

        # registering only event dependencies
        for cls_event, cls_value in get_registered_methods(klass, self._signal):
            self._signal.dependencies_by_event[cls_event].update(cls_value.depends_on)

        return klass

    def cls_fn(
        self,
        on_event: str | None | AnyFunc,
        depends_on: set[str] | None = None,
    ) -> AnyFunc:
        if callable(on_event):
            return self._setattr(on_event)

        def wrapper(fn: AnyFunc) -> AnyFunc:
            return self._setattr(fn, on_event, depends_on)

        return wrapper

    method = cls_fn

    def _get_fn_wrapper(
        self, event: str | None = None, depends_on: set[str] | None = None
    ) -> AnyFunc:
        def wrapper(fn: AnyFunc) -> AnyFunc:
            self._signal.fn_by_event[event].append(
                FnInformation(fn=fn, depends_on=depends_on or set())
            )
            return fn

        return wrapper

    def fn(
        self,
        on_event: str | None | AnyFunc,
        depends_on: set[str] | None = None,
    ) -> AnyFunc:
        if callable(on_event):
            return self._get_fn_wrapper()(on_event)

        return self._get_fn_wrapper(on_event, depends_on)
