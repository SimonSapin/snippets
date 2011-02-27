"""

    Tests for the event loop.

    See http://exyr.org/2011/event-loop/
    
    Author: Simon Sapin
    License: BSD

"""
import unittest
import os
import time
import logging
from decimal import Decimal

from event_loop import Timer, TimerManager, EventLoop
from packet_reader import PacketReader


class TestingTimeFunction(object):
    """
    An instance can be used as a dummy time function for tests.
    Tests can then set the "time" independently of real time.
    """
    def __init__(self):
        self.time = 0
    
    def __call__(self):
        # Absolute value should not matter
        return self.time + 42.25
    

class MockCallback(object):
    """
    A callback object that tells you how many times it was called.
    """
    def __init__(self):
        self.nb_calls = 0
    
    def __call__(self):
        self.nb_calls += 1


class FileLike(object):
    """
    A "file-like" object with just `fileno()`
    """
    def __init__(self, fd):
        self.fd = fd
    
    def fileno(self):
        return self.fd


class TestTimer(unittest.TestCase):

    def test_non_repeating(self):
        self._non_repeating(decorate=False)
    
    def test_decorate(self):
        self._non_repeating(decorate=False)
    
    def _non_repeating(self, decorate):
        for delay in (0, 1):
            time = TestingTimeFunction()
            callback = MockCallback()
            if decorate:
                timer = Timer.decorate(10, _time_function=time)(callback)
            else:
                timer = Timer(callback, 10, _time_function=time)
            
            still_alive = timer.run()
            assert still_alive
            assert callback.nb_calls == 0
            assert timer.sleep_time() == 10
            
            # Not yet
            time.time = 9
            
            still_alive = timer.run()
            assert still_alive
            assert callback.nb_calls == 0
            assert timer.sleep_time() == 1

            # Either just on time or after
            time.time = 10 + delay
            
            assert timer.sleep_time() == 0
            still_alive = timer.run()
            assert not still_alive
            assert callback.nb_calls == 1
            assert timer.sleep_time() == Decimal('inf')

            # More runs do nothing
            still_alive = timer.run()
            assert not still_alive
            assert callback.nb_calls == 1
            assert timer.sleep_time() == Decimal('inf')

            time.time = 15
            
            still_alive = timer.run()
            assert not still_alive
            assert callback.nb_calls == 1
            assert timer.sleep_time() == Decimal('inf')

    def test_cancel(self):
        time = TestingTimeFunction()
        callback = MockCallback()
        timer = Timer(callback, 10, _time_function=time)
        
        time.time = 9

        still_alive = timer.run()
        assert still_alive
        assert timer.sleep_time() == 1

        timer.cancel()

        still_alive = timer.run()
        assert not still_alive
        assert callback.nb_calls == 0
        assert timer.sleep_time() == Decimal('inf')

    def test_reset_early(self):
        time = TestingTimeFunction()
        callback = MockCallback()
        timer = Timer(callback, 10, _time_function=time)
        
        time.time = 7

        assert timer.sleep_time() == 3
        timer.reset()
        assert timer.sleep_time() == 10
        
        time.time = 16
        
        still_alive = timer.run()
        assert still_alive
        # reset delayed the trigger.
        assert callback.nb_calls == 0
        assert timer.sleep_time() == 1

        time.time = 17

        assert timer.sleep_time() == 0
        still_alive = timer.run()
        assert not still_alive
        assert callback.nb_calls == 1
        assert timer.sleep_time() == Decimal('inf')

    def test_reset_late(self):
        time = TestingTimeFunction()
        callback = MockCallback()
        timer = Timer(callback, 10, _time_function=time)
        
        time.time = 13

        assert timer.sleep_time() == 0
        still_alive = timer.run()
        assert not still_alive
        assert callback.nb_calls == 1
        assert timer.sleep_time() == Decimal('inf')
        
        timer.reset()

        # reset brings back a "dead" timer.
        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 1
        assert timer.sleep_time() == 10

        time.time = 21
        
        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 1
        assert timer.sleep_time() == 2

        time.time = 30

        assert timer.sleep_time() == 0
        still_alive = timer.run()
        assert not still_alive
        assert callback.nb_calls == 2
        assert timer.sleep_time() == Decimal('inf')

    def test_repeating(self):
        time = TestingTimeFunction()
        callback = MockCallback()
        timer = Timer(callback, 10, repeat=True, _time_function=time)
        
        time.time = 7

        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 0
        assert timer.sleep_time() == 3

        time.time = 34

        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 1
        assert timer.sleep_time() == 6

        time.time = 40

        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 2
        assert timer.sleep_time() == 10

    def test_cancel_repeating(self):
        time = TestingTimeFunction()
        callback = MockCallback()
        timer = Timer(callback, 10, repeat=True, _time_function=time)
        
        time.time = 10
        timer.run()
        time.time = 34

        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 2
        assert timer.sleep_time() == 6

        time.time = 40
        timer.cancel()

        for time.time in (40, 43, 60, 138):
            still_alive = timer.run()
            assert not still_alive
            assert callback.nb_calls == 2
            assert timer.sleep_time() == Decimal('inf')

    def test_reset_repeating(self):
        time = TestingTimeFunction()
        callback = MockCallback()
        timer = Timer(callback, 10, repeat=True, _time_function=time)
        
        time.time = 12

        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 1
        assert timer.sleep_time() == 8

        timer.reset()
        assert timer.sleep_time() == 10

        time.time = 34
        assert timer.sleep_time() == 0
        
        timer.reset()
        assert timer.sleep_time() == 10
        
        still_alive = timer.run()
        assert still_alive
        assert callback.nb_calls == 1
        assert timer.sleep_time() == 10
        


class TestTimerManager(unittest.TestCase):

    def test_empty_timer_list(self):
        manager = TimerManager()
        assert manager.sleep_time() == Decimal('inf')
    
    def test_invalid_timeouts(self):
        manager = TimerManager()
        self.assertRaises(AssertionError, manager.add_timer, 0, None)
        self.assertRaises(AssertionError, manager.add_timer, -1, None)
    
    def test_single_timer(self):
        time = TestingTimeFunction()
        manager = TimerManager(_time_function=time)
        callback = MockCallback()
        manager.add_timer(30, callback)
        
        assert manager.sleep_time() == 30
        assert callback.nb_calls == 0
        
        manager.run()
        assert callback.nb_calls == 0

        time.time = 22
        assert manager.sleep_time() == 8

        manager.run()
        assert callback.nb_calls == 0

        time.time = 30
        assert manager.sleep_time() == 0

        manager.run()
        assert callback.nb_calls == 1
        # Timer was removed from the list
        assert manager.sleep_time() == Decimal('inf')

        time.time = 100
        manager.run()
        # not called a second time
        assert callback.nb_calls == 1

    def test_single_repeating_timer(self):
        time = TestingTimeFunction()
        manager = TimerManager(_time_function=time)
        callback = MockCallback()
        manager.add_timer(30, callback, repeat=True)
        
        assert manager.sleep_time() == 30
        assert callback.nb_calls == 0
        
        manager.run()
        assert callback.nb_calls == 0

        time.time = 22
        assert manager.sleep_time() == 8

        manager.run()
        assert callback.nb_calls == 0

        time.time = 30
        assert manager.sleep_time() == 0

        manager.run()
        assert callback.nb_calls == 1
        # Timer was NOT removed from the list
        assert manager.sleep_time() == 30

        time.time = 71
        assert manager.sleep_time() == 0
        manager.run()
        assert callback.nb_calls == 2
        assert manager.sleep_time() == 19

        # "Wait" more than one interval
        time.time = 200
        assert manager.sleep_time() == 0
        manager.run()
        # Only called once more
        assert callback.nb_calls == 3
        # Next is at t = 21
        assert manager.sleep_time() == 10


    def test_long_callback(self):
        time = TestingTimeFunction()
        manager = TimerManager(_time_function=time)
        
        def loose_time():
            time.time += 11
            
        manager.add_timer(2, loose_time, repeat=True)

        manager.run()
        assert time.time == 0

        time.time = 2
        manager.run()
        assert time.time == 13
        # t = 4, 6, 8 were skipped, t = 12 is late but ready
        assert manager.sleep_time() == 0
    
    def test_many(self):
        time = TestingTimeFunction()
        manager = TimerManager(_time_function=time)

        c5 = MockCallback()
        manager.add_timer(5, c5, repeat=True)
        c7 = MockCallback()
        manager.add_timer(7, c7, repeat=True)
        c13 = MockCallback()
        manager.add_timer(13, c13, repeat=True)
        
        nb_sleeps = 0
        while 1:
            time.time += manager.sleep_time()
            if time.time >= 100:
                break
            nb_sleeps += 1
            manager.run()
        
        assert c5.nb_calls == 19
        assert c7.nb_calls == 14
        assert c13.nb_calls == 7
        # 4 is the number of times (t = 35, 65, 70, 91) where 2 timers
        # trigger at the same time.
        assert nb_sleeps == (c5.nb_calls + c7.nb_calls + c13.nb_calls - 4)

    def test_contsant_sleep(self):
        time = TestingTimeFunction()
        manager = TimerManager(_time_function=time)

        c5 = MockCallback()
        manager.add_timer(5, c5, repeat=True)
        c7 = MockCallback()
        manager.add_timer(7, c7, repeat=True)
        c13 = MockCallback()
        manager.add_timer(13, c13, repeat=True)
        
        
        for time.time in xrange(100):
            # manager.sleep_time() is optimal, but calling run() more often
            # also works. (Here every "second")
            manager.run()
            
            if time.time == 42:
                def check_time():
                    assert time.time == 48
                one_shot = MockCallback()
                manager.add_timer(6, check_time)
                manager.add_timer(6, one_shot)
        
        assert c5.nb_calls == 19
        assert c7.nb_calls == 14
        assert c13.nb_calls == 7
        assert one_shot.nb_calls == 1


class TestEventLoop(unittest.TestCase):
    def _simple(self, reader, writer):
        loop = EventLoop()
        nb_reads = [0]

        @loop.block_reader(reader)
        def incoming(data):
            assert data == 'foo'
            nb_reads[0] += 1
            loop.stop()
        
        assert os.write(writer, 'foo') == 3
        loop.run()
        assert nb_reads[0] == 1

    def test_simple_pipe(self):
        reader, writer = os.pipe()
        try:
            self._simple(reader, writer)
        finally:
            os.close(reader)
            os.close(writer)

    def test_filelike(self):
        reader, writer = os.pipe()
        try:
            self._simple(FileLike(reader), writer)
        finally:
            os.close(reader)
            os.close(writer)

    def test_pipe(self):
        reader, writer = os.pipe()
        try:
            loop = EventLoop()
            nb_reads = [0]
            nb_writes = [0]
            
            duration = .1
            interval = .0095
            expected_nb = 10
            assert expected_nb == duration // interval
            # Avoid a race condition between the loop stop and the last read.
            assert expected_nb < duration / interval
            
            start = time.time()
            loop.add_timer(duration)(loop.stop)
            
            @loop.add_timer(interval, repeat=True)
            def write_something():
                assert os.write(writer, 'foo') == 3
                nb_writes[0] += 1

            @loop.block_reader(reader)
            def incoming(data):
                assert data == 'foo'
                nb_reads[0] += 1
            
            loop.run()
            assert round(time.time() - start, 2) == duration
            assert nb_writes[0] == expected_nb, nb_writes
            assert nb_reads[0] == expected_nb, nb_reads
        finally:
            os.close(reader)
            os.close(writer)


class TestLineReader(unittest.TestCase):
    def test_line_reader(self):
        reader, writer = os.pipe()
        try:
            loop = EventLoop()
            
            data = [
                'Lorem ipsum\n',
                'dolor\nsit\namet, ',
                'consectetur',
                ' adipiscing ',
                'elit.\nAliquam magna dolor, ', # no newline character at the end
            ]
            # Reverse because list.pop() pops at the end.
            data = data[::-1]
            
            start = time.time()
            @loop.add_timer(.01, repeat=True)
            def slow_write():
                if data:
                    d = data.pop()
                    assert os.write(writer, d) == len(d)
                else:
                    loop.stop()
            
            lines = []
            loop.line_reader(reader, max_block_size=5)(lines.append)
                
            loop.run()
            
            assert lines == [
                'Lorem ipsum\n',
                'dolor\n',
                'sit\n',
                'amet, consectetur adipiscing elit.\n'
            ]
        finally:
            os.close(reader)
            os.close(writer)
        
    def test_timing(self):
        reader, writer = os.pipe()
        try:
            loop = EventLoop()
            
            data = [
                'Lorem ipsum\n',
                'dolor\nsit\namet, ',
                'consectetur',
                ' adipiscing ',
                'elit.\nAliquam magna dolor, ', # no newline character at the end
            ]
            # Reverse because list.pop() pops at the end.
            data = data[::-1]
            
            @loop.add_timer(.01, repeat=True)
            def slow_write():
                if data:
                    os.write(writer, data.pop())
                else:
                    loop.stop()
            
            lines = []
            @loop.line_reader(reader)
            def new_line(line):
                lines.append(line)
                expected_time = {
                    'L': .01, 'd': .02, 's': .02, 'a': .05}[line[0]]
                assert round(time.time() - start, 2) == expected_time

            time.sleep(.02)
            # Reset so that the timing is correct in spite of the sleep we
            # just did.
            slow_write.reset()
            start = time.time()
            loop.run()
            
            assert lines == [
                'Lorem ipsum\n',
                'dolor\n',
                'sit\n',
                'amet, consectetur adipiscing elit.\n'
            ]
        finally:
            os.close(reader)
            os.close(writer)
        
        
class TestPushBack(unittest.TestCase):
    def test_push_back(self):
        reader, writer = os.pipe()
        try:
            data = 'Lorem ipsum dolor sit.'
            assert os.write(writer, data) == len(data)
            
            loop = EventLoop()
            
            state = [1]
            
            @loop.push_back_reader(reader, max_block_size=5)
            def new_block(data, push_back):
                if state[0] == 1:
                    assert data == 'Lorem'
                elif state[0] == 2:
                    assert data == ' ipsu'
                    push_back(data)
                elif state[0] == 3:
                    assert data == ' ipsum dol'
                    push_back('d')
                    push_back('ol')
                elif state[0] == 4:
                    assert data == 'dolor si'
                elif state[0] == 5:
                    assert data == 't.'
                    loop.stop()
                else:
                    assert False
                state[0] += 1
            
            loop.run()
            assert state[0] == 6
        finally:
            os.close(reader)
            os.close(writer)


class TestPacketReader(unittest.TestCase):
    def test_packets(self):
        reader, writer = os.pipe()
        try:
            loop = EventLoop()
            original_packets = [
                'foo',
                '',
                'Lorem ipsum dolor sit amet.',
                '42',
            ]
            packets = []

            def callback(packet):
                packets.append(packet)
                assert packet_reader.dropped_bytes == {
                    1: 0,  2: 1,  3: 3,  4: 6
                }[len(packets)]
                if len(packets) == len(original_packets):
                    loop.stop()

            def write(data):
                assert os.write(writer, data) == len(data)
                
            for i, packet in enumerate(original_packets):
                write('blah'[:i]) # non-packet garbage
                write(PacketReader.PACKET_DELIMITER)
                write(chr(len(packet) + 1))
                write(packet)
                
            # Choose a very small block size on purpose to (hopefully)
            # test more code paths such as half packets
            packet_reader = PacketReader(loop, reader, callback,
                                         max_block_size=3)
            loop.run()
            assert packets == original_packets
        finally:
            os.close(reader)
            os.close(writer)
        
        

if __name__ == '__main__':
    unittest.main()
