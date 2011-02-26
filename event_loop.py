import sys
import os
import time
import math


class TimerManager(object):
    """
    TimerManager handle multiple timers.

    Not thread-safe, but the point is to avoid threads anyway.
    """
    def __init__(self, _time_function=time.time):
        """
        `_time_function` is meant as a dependency injection for testing.
        """
        self._timers = []
        self._now = _time_function
        
    def add_timer(self, timeout, callback, repeat=False):
        """
        Add a timer with `callback`, expiring `timeout` seconds from now and,
        if `repeat` is true, every `timeout` seconds after that.
        """
        assert timeout > 0
        next = self._now() + timeout # Next time this timer expires
        interval = timeout if repeat else None
        self._timers.append((next, interval, callback))
    
    def run(self):
        """
        Call without arguments the callback of every expired timer.
        
        Each callback is called at most once, even if a repeating timer
        expired several times since last time `run()` was called.
        """
        indices_to_remove = []
        
        for index, (next, interval, callback) in enumerate(self._timers):
            if next > self._now():
                continue
            callback()
            if interval:
                # Repeating timer: update the expiry time.
                # Has expired that many times since last run().
                # Call self._now() again since callback() may have taken time.
                times = (self._now() - next) // interval + 1
                next += times * interval
                self._timers[index] = (next, interval, callback)
            else:
                # Not repeating: remove.
                # Removing disrupts iteration: do it later.
                indices_to_remove.append(index)
        
        # indices_to_remove is in increasing order.
        # Remove in decreasing order since removing changes the meaning of
        # greater indices.
        for index in reversed(indices_to_remove):
            del self._timers[index]
    
    def sleep_time(self):
        """
        How much time you can wait before `run()` does something.
        Raises ValueError if no timer is registered.
        """
        earliest, _, _ = min(self._timers)
        sleep = earliest - self._now()
        return sleep if sleep > 0 else 0
            

