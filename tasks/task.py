import asyncio
import inspect
from asyncio import Queue
from threading import Thread
from typing import Callable


def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    global task_queue
    asyncio.set_event_loop(loop)
    task_queue = Queue()
    loop.run_until_complete(consume_task(task_queue))


async def add_task_to_queue(fn, callback, *args, **kwargs):
    global task_queue
    await task_queue.put((fn, callback, args, kwargs))


async def consume_task(queue: Queue):
    while True:
        fn, callback, args, kwargs = await queue.get()
        try:
            if inspect.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = fn(*args, **kwargs)
            callback(result=result, error=None)
        except Exception as err:
            callback(result=None, error=err)
        queue.task_done()


task_queue: Queue = None
task_loop = asyncio.new_event_loop()
task_thread = Thread(target=start_background_loop, args=(task_loop,), daemon=True)
task_thread.start()


class Task:
    is_active = False

    def do_task(self, filepath) -> str:
        return filepath
