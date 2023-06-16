import typing as t

if t.TYPE_CHECKING:
    from src.base_signal import Signal


class Reactive:
    """A reactive object that can be used to trigger events when its value changes"""

    def __init__(
        self,
        signal: "Signal",
        data: t.Any,
    ):
        self._data = data
        self._signal = signal

    def get(self) -> t.Any:
        """
        Get the value of the reactive object
        Returns:

        """
        return self._data

    def set(self, data: t.Any, **kwargs: t.Any) -> t.Any:
        """
        Set the value of the reactive object
        firing the signal if the value changes
        Args:
            data:

        Returns:

        """
        if isinstance(data, t.Mapping):
            if not isinstance(self._data, t.Mapping):
                raise TypeError("Mapping awaited")
            self._data = {**self._data, **data}
        else:
            self._data = data
        return self._signal.fire(**kwargs)(self._data)
