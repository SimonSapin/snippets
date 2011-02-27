"""

    If an application needs to wait for various events and polling is not
    possible or desirable, one solution is to use a blocking threads for each
    events. However, multi-threading comes with its pitfalls and problems.
    
    This event loop is a framework that allows an application to wait for
    various events without using threads. Currently supported events are
    files being ready for reading and timers (repeating or not).
    
    The heart of the loop is basically `select.select()` with a well-chosen
    timeout.
    
    See http://exyr.org/2011/event-loop/
    
    Author: Simon Sapin
    License: BSD

"""
import sys
import os
import time
import itertools
import select
import decimal


# float('inf') is only officially supported form Python 2.6, while decimal
# is there since 2.4.
Infinity = decimal.Decimal('Infinity')


class Timer(object):
    """
    Create a new timer.
    If it's `run()` method is called often enough, `callback` will be called
    (without parameters) `interval` seconds from now (may be a floating point
    number) and, if `repeat` is true, every `interval` seconds after that.
    
    There is no thread or other form of preemption: the callback won't be
    called if `run()` is not.
    
    A repeating timers may miss a few beats if `run()` is not called for more
    than one interval but is still scheduled for whole numbers of interval
    after is was created or reset. See the tests for examples
    """
    
    @classmethod
    def decorate(cls, *args, **kwargs):
        """
        Decorator factory:
        
            @Timer.decorate(1, repeat=True)
            def every_second():
                # ...
        
        The decorated function is replaced by the Timer object so you can
        write eg.
        
            every_second.cancel()
        """
        def decorator(callback):
            return cls(callback, *args, **kwargs)
        return decorator

    def __init__(self, callback, interval, repeat=False,
                 _time_function=time.time):
        # `_time_function` is meant as a dependency injection for testing.
        assert interval > 0
        self._callback = callback
        self._interval = interval
        self._repeat = repeat
        self._now = _time_function
        self.reset()
    
    def reset(self):
        """
        Cancel currently scheduled expiry and start again as if the timer
        was created just now.
        """
        self._expiry = self._now() + self._interval
        
    def cancel(self):
        """Cancel the timer. The same timer object should not be used again."""
        self._expiry = None
        
    def __call__(self):
        """Decorated callbacks can still be called at any time."""
        self._callback()
    
    def run(self):
        """
        Return whether the timer will trigger again. (Repeating or not expired
        yet.)
        """
        if self._expiry is None:
            return False
        if self._now() < self._expiry:
            return True
        if self._repeat:
            # Would have expired that many times since last run().
            times = (self._now() - self._expiry) // self._interval + 1
            self._expiry += times * self._interval
        else:
            self._expiry = None
        # Leave a chance to the callback to call `reset()`.
        self()
        return self._expiry is not None
    
    def sleep_time(self):
        """
        Return the amount of time before `run()` does anything, or
        Decimal('Infinity') for a canceled or expired non-repeating timer.
        """
        if self._expiry is None:
            return Infinity
        else:
            return max(self._expiry - self._now(), 0)


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
        self._time_function = _time_function
        
    def add_timer(self, timeout, callback, repeat=False):
        """
        Add a timer with `callback`, expiring `timeout` seconds from now and,
        if `repeat` is true, every `timeout` seconds after that.
        """
        timer = Timer(callback, timeout, repeat=repeat,
                      _time_function= self._time_function)
        self._timers.append(timer)
        return timer
    
    def run(self):
        """
        Call without arguments the callback of every expired timer.
        
        Each callback is called at most once, even if a repeating timer
        expired several times since last time `run()` was called.
        """
        # Run all timers and remove those who won't trigger again.
        self._timers = [timer for timer in self._timers if timer.run()]

    
    def sleep_time(self):
        """
        How much time you can wait before `run()` does something.
        Return None if no timer is registered.
        """
        return min(itertools.chain(
            # Have at least one element. min() raises on empty sequences.
            [Infinity],
            (timer.sleep_time() for timer in self._timers)
        ))
            

class EventLoop(object):
    """
    Manage callback functions to be called on certain events.
    Currently supported events are:
    
     * Timers (same as TimerManager)
     * File descriptors ready for reading. (Waited for using `select.select()`)
    """
    def __init__(self):
        self._timers = TimerManager()
        self._readers = {}
    
    def add_timer(self, timeout, repeat=False):
        """
        Decorator factory for adding a timer:
            
            @loop.add_timer(1)
            def one_second_from_now():
                # callback code
        """
        def decorator(callback):
            return self._timers.add_timer(timeout, callback, repeat)
        return decorator
    
    def watch_for_reading(self, file_descriptor):
        """
        Decorator factory for watching a file descriptor. When the file
        descriptor is ready for reading, it is passed as a paramater to
        the decorated callback.
        
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
            file_descriptor = file_descriptor.fileno()
        
        def decorator(callback):
            self._readers[file_descriptor] = callback
            return callback
        return decorator
    
    def block_reader(self, file_descriptor, max_block_size=8 * 1024):
        """
        Decorator factory. As soon as some data is available for reading on
        the file descriptor, the decorated callback is called with a block
        of up to `max_block_size` bytes.
        
        If data comes slowly, blocks will be smaller than max_block_size and
        contain just what can be read without blocking. In that case, the value
        of max_block_size does not matter.
        """
        def decorator(callback):
            @self.watch_for_reading(file_descriptor)
            def reader(fd):
                # According to `select.select()` there is some data,
                # so os.read() won't block.
                data = os.read(fd, max_block_size)
                callback(data)
            return callback
        return decorator

    def push_back_reader(self, file_descriptor, max_block_size=8 * 1024):
        """
        Just like block_reader, but allow you to push data "back into tho file".
        Callbacks get a `push_back` function as a second parameter. You can
        push back the data you don't want to use yet.
        
        Example use case: you get some data in a block, but you need more
        before it is useful or meaningful. You can push it back instead of
        keeping track of it yourself.
        
        On the next call, the data you pushed back will be prepended to the
        next block, in the order it was pushed.
        """
        def decorator(callback):
            pushed_back = []
            
            @self.block_reader(file_descriptor, max_block_size)
            def reader(data):
                if pushed_back:
                    pushed_back.append(data)
                    data = ''.join(pushed_back)
                    pushed_back[:] = []
                callback(data, pushed_back.append)
            return callback
        return decorator
            
    def line_reader(self, file_descriptor, max_block_size=8 * 1024):
        r"""
        Decorator factory. The decorated callback is called once with
        every line (terminated by '\n') as they become available.
        
        Just like with `some_file.readline()`, the trailing newline character
        is included.
        
        The `max_block_size` paramater is just passed to `block_reader()`.
        """
        # line_reader could be implemeted with push_back_reader, but not doing
        # so allow us to only search new data for the newline chararcter.
        def decorator(callback):
            partial_line_fragments = []
            
            @self.block_reader(file_descriptor, max_block_size)
            def reader(data):
                # Loop since there could be more than one line in one block.
                while 1:
                    try:
                        end = data.index('\n')
                    except ValueError:
                        # no newline here
                        break
                    else:
                        end += 1 # include the newline char
                        partial_line_fragments.append(data[:end])
                        line = ''.join(partial_line_fragments)
                        partial_line_fragments[:] = []
                        callback(line)
                        data = data[end:]
                if data:
                    partial_line_fragments.append(data)
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
            if timeout == Infinity:
                timeout = None
            if self._readers:
                ready, _, _ = select.select(
                    self._readers.keys(), [], [], timeout)
            else:
                assert timeout is not None, 'Running without any event'
                # Some systems do not like 3 empty lists for select()
                time.sleep(timeout)
                ready = []
            self._timers.run()
            for fd in ready:
                self._readers[fd](fd)

    def stop(self):
        """
        Signal the event loop to stop before doing another iteration.
        
        Since the point of the event loop is to avoid threads, this will
        probably be called from an event callback.
        """
        self._running = False


if __name__ == '__main__':
    loop = EventLoop()
    
    @loop.add_timer(5, repeat=True)
    def timeout():
        print 'No new line in 5 seconds. Stopping now.'
        loop.stop()
    
    @loop.line_reader(sys.stdin)
    def new_line(line):
        timeout.reset()
        print 'Echo:', line.strip()
        
    print 'Echoing lines.'
    loop.run()
    print 'Exit.'
