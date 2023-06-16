import asyncio
import threading
import typing as t
from uuid import uuid4

from rustshed import Err, Null, Ok, Option, Result

from src._firing import _Fire

if t.TYPE_CHECKING:
    from src.base_signal import Signal


class JobHandle:
    """
    A handle to a job that can be used to cancel it, wait for its result, etc.
    """

    def __init__(self):
        self._job_id = uuid4()
        self._result: Option[Result] = Null
        self._result_event = asyncio.Event()
        self._cancel_event = asyncio.Event()

    @property
    def job_id(self):
        """
        Get the job id

        Returns:
            _type_: _description_
        """
        return self._job_id

    async def wait_for_result(self):
        """
        Wait for the result of the job

        Returns:
            _type_: _description_
        """
        await self._result_event.wait()
        return self._result

    async def cancel(self):
        """
        Cancel the job
        Note: we wait for the job to be cancelled before returning
        """
        self._cancel_event.set()
        await asyncio.sleep(0.1)


class BackendCallable(_Fire):
    def __init__(self, backend: "BackendProtocol", *args: t.Any, **kwargs: t.Any):
        super().__init__(backend._signal, *args, **kwargs)
        self.backend = backend

    async def __call__(self, *args: t.Any, **kwds: t.Any) -> t.Any:
        """
        Find callback to call from the signal and send it to the backend

        Returns:
            t.Any: _description_
        """
        job_handles = []
        for fn_information in self._find_fn_to_fire():
            job_handle = JobHandle()
            await self.backend.put((job_handle, fn_information.fn, args, kwds))
            job_handles.append(job_handle)
        return job_handles


class BackendProtocol(t.Protocol):
    _signal: "Signal"
    _consumer: "ConsumerProtocol"

    async def poll(self) -> t.Any:
        """
        Polls a job from the backend

        Returns:
            t.Any: _description_
        """
        ...

    async def put(self, data: t.Any) -> None:
        """
        Puts a job into the backend

        Args:
            data (t.Any): _description_
        """
        ...

    def fire(self, *args: t.Any, **kwargs: t.Any) -> BackendCallable:
        """
        Fires the signal with the given arguments

        Returns:
            BackendCallable: _description_
        """
        return BackendCallable(self, *args, **kwargs)

    @property
    def default_consumer(self) -> "ConsumerProtocol":
        """
        Returns the default consumer for this backend

        Returns:
            ConsumerProtocol: _description_
        """
        return self._consumer


class ConsumerProtocol(t.Protocol):
    async def dequeue(self) -> t.AsyncGenerator[t.Any, None]:
        """
        Dequeues a job from the backend and yields it to the caller

        Returns:
            t.AsyncGenerator[t.Any, None]: _description_
        """
        ...

    async def run_task(
        self, fn: t.Callable[..., t.Any], *args: t.Any, **kwargs: t.Any
    ) -> Ok[t.Any] | Err[Exception]:
        """

        Args:
            fn (t.Callable[..., t.Any]): _description_

        Returns:
            Ok[t.Any] | Err[Exception]: _description_
        """
        ...

    async def run(self) -> None:
        """
        Starts the consumer main function
        """
        ...

    def start_in_thread(self, daemon: bool = False) -> None:
        """
        Starts the consumer in a separate thread.
        Args:
            daemon (bool, optional): _description_. Defaults to False.
        """

        def thread_consumer(loop):
            future = asyncio.run_coroutine_threadsafe(self.run(), loop)
            try:
                future.result()
            except Exception as err:
                print(err)

        threading.Thread(
            target=thread_consumer, args=(asyncio.get_event_loop(),), daemon=True
        ).start()
