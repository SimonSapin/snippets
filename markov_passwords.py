# coding: utf8
import string, itertools, random

def char_iterator(file):
    """
    The default iterator for files yields lines.
    This one yields single characters.
    """
    return iter(lambda: file.read(1), '')
    
def closing_iterator(iterable, close):
    for i in iterable:
        yield i
    close()

def read_chars(filename):
    f = open(filename)
    return closing_iterator(char_iterator(f), f.close)

    
def get_letter_positions(alphabet, characters):
    """
    Map characters to their position in alphabet and filter out these
    that are not in alphabet.
    
    >>> list(get_letter_positions('abc', 'b + c = a'))
    [1, 2, 0]
    """
    # str.find returns -1 for "not found"
    return (p for p in (alphabet.find(c) for c in characters) if p >= 0)

def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    # stolen from http://docs.python.org/library/itertools.html#recipes
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)

class MarkovFrequencies(object):
    def __init__(self, frequencies):
        # frequencies[p][s] is the number of times that s appeared after p
        # in states.
        self.frequencies = [(f, sum(f)) for f in frequencies]
    
    @classmethod
    def from_chain(cls, nb_states, chain):
        """
        chain must be an iterable of state integers
        so that 0 <= state < nb_states
        """
        def assert_range(chain):
            for s in chain:
                assert 0 <= s < nb_states
                yield s
        chain = assert_range(chain)
        # We can’t use [[0] * nb_states] * nb_states as the inner
        # lists would all be references to a single mutable object
        frequencies = [[0] * nb_states for i in xrange(nb_states)]
        for previous, current in pairwise(chain):
            if previous is not None:
                frequencies[previous][current] += 1
        
        return cls(frequencies)

    def next(self, state):
        frequencies, total = self.frequencies[state]
        rand = random.random() * total
        for next_state, frequency in enumerate(frequencies):
            if rand < frequency:
                return next_state
            rand -= frequency
    
    def make_chain(self, initial_state):
        state = initial_state
        while True:
            state = self.next(state)
            yield state


class TextMarkovFrequencies(object):
    def __init__(self, alphabet, chars):
        chain = get_letter_positions(alphabet, chars)
        self.frequencies = MarkovFrequencies.from_chain(len(alphabet), chain)
        self.alphabet = alphabet

    def make_chain(self, initial_letter):
        initial_state = self.alphabet.find(initial_letter)
        assert initial_state >= 0 # ie. initial_letter in self.alphabet
        return (
            self.alphabet[state] for state in
            self.frequencies.make_chain(initial_state)
        )

def text():
    f = TextMarkovFrequencies(string.ascii_letters + ',.- ', read_chars('english'))
    print ''.join(itertools.islice(f.make_chain(' '), 200))

def word():
    f = TextMarkovFrequencies(string.ascii_lowercase, read_chars('japanese'))
    print ''.join(itertools.islice(f.make_chain('a'), 14))

def main():
    word()

if __name__ == '__main__':
    main()

