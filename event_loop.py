import sys
import os
import time
import math


class TimerManager(object):
    """
    Not thread-safe, but the point is to avoid threads anyway.
    """
    def __init__(self):
        self._timers = []
        
    def add_timer(self, timeout, callback, repeat=False):
        """
        Add a timer with `callback` to expire in `timeout` seconds.
        The timer is recurring if `repeat` is true.
        """
        assert timeout > 0
        next = time.time() + timeout # Next time this timer expires
        interval = timeout if repeat else None
        self._timers.append((next, interval, callback))
    
    def run(self):
        """
        Handle timers that have expired
        """
        indices_to_remove = []
        
        for index, (next, interval, callback) in enumerate(self._timers):
            if next > time.time():
                continue
            callback()
            if interval:
                # Repeating timer: update the expiry time.
                next += math.ceil((time.time() - next) / interval) * interval
                self._timers[index] = (next, interval, callback)
            else:
                # Not repeating: remove.
                # Removing disrupts iteration: do it later.
                indices_to_remove.append(index)
        
        # Indices_to_remove is in increasing order.
        # Remove in decreasing order since removing changes the meaning of
        # greater indices.
        for index in reversed(indices_to_remove):
            del self._timers[index]
    
    def sleep_time(self):
        """
        How much time you can wait before `run()` does something.
        """
        earliest, _, _ = min(self._timers)
        sleep = earliest - time.time()
        return sleep if sleep > 0 else 0
            

def test_timers():
    manager = TimerManager()
    start = time.time()
    
    def printer(message, interval):
        def callback():
            t = time.time() - start
            print t, t % interval, message
        return callback

    manager.add_timer(5, printer('5 seconds', 5))
    manager.add_timer(1, printer('1 second timer', 1), repeat=True)
    manager.add_timer(1.3, printer('1.3 second timer', 1.3), repeat=True)
    
    while 1:
        time.sleep(manager.sleep_time() + 0.1)
        manager.run()


def main():
    test_timers()
    
if __name__ == '__main__':
    main()
