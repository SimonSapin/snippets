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
        self._readers = {}
    
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
    
    @loop.line_reader(sys.stdin)
    def new_line(line):
        line = line.strip()
        if line == 'exit':
            loop.stop()
        print line
    
    @loop.add_timer(5, repeat=True)
    def five():
        print '5 seconds passed.'
    
    print 'Echoing lines. Type "exit" to stop.'
    loop.run()
