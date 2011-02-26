"""

    Tests for the event loop.
    
    Author: Simon Sapin
    License: BSD

"""
import unittest
import os
import time

from event_loop import TimerManager, EventLoop


class TestingTimeFunction(object):
    """
    An instance can be used as a dummy time function for tests.
    Tests can then set the "time" independently of real time.
    """
    def __init__(self):
        self.time = 0
    
    def __call__(self):
        # Absolute value should not matter
        return self.time + 42


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


class TestTimerManager(unittest.TestCase):

    def test_empty_timer_list(self):
        manager = TimerManager()
        assert manager.sleep_time() is None
    
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
        assert manager.sleep_time() is None

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
        # t = 4, 6, 8, 12 were skipped, next is t = 14
        assert manager.sleep_time() == 1
    
    def test_many(self):
        time = TestingTimeFunction()
        manager = TimerManager(_time_function=time)

        c5 = MockCallback()
        manager.add_timer(5, c5, repeat=True)
        c7 = MockCallback()
        manager.add_timer(7, c7, repeat=True)
        c13 = MockCallback()
        manager.add_timer(13, c13, repeat=True)
        
        while 1:
            time.time += manager.sleep_time()
            if time.time >= 100:
                break
            manager.run()
        
        assert c5.nb_calls == 19
        assert c7.nb_calls == 14
        assert c13.nb_calls == 7

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
            
            start = time.time()
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


if __name__ == '__main__':
    unittest.main()
