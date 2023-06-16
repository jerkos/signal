import asyncio
import typing as t

from rustshed import Err, Ok, Some

from src.base_signal import Signal
from src.queueing.backend import BackendProtocol, ConsumerProtocol, JobHandle


class QueueConsumer(ConsumerProtocol):
    def __init__(self, backend: BackendProtocol):
        self._backend = backend

    async def dequeue(self):
        while True:
            yield await self._backend.poll()

    async def run_task(
        self, fn: t.Callable[..., t.Any], *args: t.Any, **kwargs: t.Any
    ) -> Ok[t.Any] | Err[Exception]:
        async with asyncio.Semaphore(3):
            try:
                return Ok(await fn(*args, **kwargs))
            except Exception as err:
                return Err(err)

    @staticmethod
    def _done_callback(
        task: asyncio.Task, cancel_task: asyncio.Task, job_handle: JobHandle
    ):
        if not task.cancelled():
            cancel_task.cancel()
            job_handle._result = Some(task.result())
            job_handle._result_event.set()

    @staticmethod
    def _cancel_callback(task: asyncio.Task, result_task: asyncio.Task):
        if not task.cancelled():
            result_task.cancel()

    async def run(self):
        async for job_handle, fn, fn_args, fn_kwargs in self.dequeue():
            task = asyncio.create_task(self.run_task(fn, *fn_args, **fn_kwargs))
            cancel_event: asyncio.Event = job_handle._cancel_event
            cancel_task = asyncio.create_task(cancel_event.wait())
            task.add_done_callback(
                lambda t: self._done_callback(t, cancel_task, job_handle)
            )
            cancel_task.add_done_callback(lambda t: self._cancel_callback(t, task))
            await asyncio.wait({task, cancel_task}, return_when=asyncio.FIRST_COMPLETED)


class QueueBackend(BackendProtocol):
    def __init__(self, signal: "Signal", consumer: ConsumerProtocol | None = None):
        self._signal = signal
        self._queue: asyncio.Queue[t.Any] = asyncio.Queue()
        self._consumer = consumer or QueueConsumer(self)

    async def poll(self):
        return await self._queue.get()

    async def put(self, data: t.Any):
        await self._queue.put(data)
