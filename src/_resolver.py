import typing as t

if t.TYPE_CHECKING:
    from src.base_signal import Signal


class _Resolver:
    def __init__(self, signal: "Signal"):
        self._signal = signal

    def resolve(
        self,
        target_event: str | None,  # always a string
        _results: list[list[str | None]],
        _path: list[str | None] | None = None,
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
                self.resolve(dependency, _results, new_path)
