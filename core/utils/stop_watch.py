import time

from core.utils import asyncme


class StopWatch:
    is_running = False
    elapsed = 0
    end = 0
    is_cancelled = False

    def __init__(self):
        self.elapsed = None
        self.kwargs = None
        self.args = None
        self.func = None

    def start_or_reset(self, time_in_sec, func, *args, **kwargs):
        self.end = time_in_sec
        self.is_cancelled = False
        self.func = func
        self.args = args
        self.kwargs = kwargs
        if self.is_running:
            self.elapsed = 0
        else:
            self.is_running = True
            self.begin_loop()

    def cancel(self):
        self.is_cancelled = True
        self.is_running = False

    @asyncme.run_or_none
    def begin_loop(self):
        while self.is_running and self.elapsed < self.end:
            time.sleep(1)
            self.elapsed += 1
        if not self.is_cancelled:
            self.func(*self.args, **self.kwargs)
