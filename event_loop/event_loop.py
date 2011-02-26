"""

    If an application needs to wait for various events and polling is not
    possible or desirable, one solution is to use a blocking threads for each
    events. However, multi-threading comes with its pitfalls and problems.
    
    This event loop is a framework that allows an application to wait for
    various events without using threads. Currently supported events are
    files being ready for reading and timers (repeating or not).
    
    The heart of the loop is basically `select.select()` with a well-chosen
    timeout.
    
    Author: Simon Sapin
    License: BSD

"""
import sys
import os
import time
import select


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
        Return None if no timer is registered.
        """
        if not self._timers:
            return None
        earliest, _, _ = min(self._timers)
        sleep = earliest - self._now()
        return sleep if sleep > 0 else 0
            

class EventLoop(object):
    """
    Manage callback functions to be called on certain events.
    Currently supported events are:
    
     * Timers (same as TimerManager)
     * File descriptors ready for reading. (Waited for using `select.select()`)
    """
    def __init__(self):
        self._timers = TimerManager()
        self._running = False
        self._file_descriptors = []
        self._callbacks = {}
    
    def add_timer(self, timeout, repeat=False):
        """
        Decorator factory for adding a timer:
            
            @loop.add_timer(1)
            def one_second_from_now():
                # callback code
        """
        def decorator(callback):
            self._timers.add_timer(timeout, callback, repeat)
            return callback
        return decorator
    
    def watch_for_reading(self, file_descriptor):
        """
        Decorator factory for watching a file descriptor. The decorated
        callback is called when the file descriptor is ready for reading.
        
        Takes either a file descriptor (integer) or a file object with a
        `fileno()` method that returns one.
            
            @loop.watch_for_reading(sys.stdin)
            def one_second_from_now():
                data = os.read(sys.stdin.fileno(), 255)
                # ...
                
        Use `os.read()` instead of `some_file.read()` to read just what is
        available and avoid blocking, without the file actually being in
        non-blocking mode.
        """
        if not isinstance(file_descriptor, (int, long)):
            file_descriptor = fd.fileno()
            
        def decorator(callback):
            self._file_descriptors.append(file_descriptor)
            self._callbacks[file_descriptor] = callback
            return callback
        return decorator
    
    def run(self):
        """
        Run the event loop. Wait for events, call callbacks when events happen,
        and only return when the `stop()` is called.
        """
        self._running = True
        while self._running:
            timeout = self._timers.sleep_time()
            if self._file_descriptors:
                ready, _, _ = select.select(
                    self._file_descriptors, [], [], timeout)
            else:
                assert timeout is not None, 'Running without any event'
                # Some systems do not like 3 empty lists for select()
                time.sleep(timeout)
                ready = []
            self._timers.run()
            for fd in ready:
                self._callbacks[fd]()

    def stop(self):
        """
        Signal the event loop to stop before doing another iteration.
        
        Since the point of the event loop is to avoid threads, this will
        probably be called from an event callback.
        """
        self._running = False


