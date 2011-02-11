# coding: utf8
import string, itertools, random

# This is a romanization of the opening of "Genji Monogatari"
# by Murasaki Shikibu.
# Source: http://etext.lib.virginia.edu/japanese/genji/roman.html
japanese = '''
Idure no ohom-toki ni ka, nyougo, kaui amata saburahi tamahi keru naka ni,
ito yamgotonaki kiha ni ha ara nu ga, sugurete tokimeki tamahu ari keri.

Hazime yori ware ha to omohi agari tamahe ru ohom-kata-gata, mezamasiki mono ni
otosime sonemi tamahu. Onazi hodo, sore yori gerahu no kaui-tati ha, masite 
yasukara zu. Asa-yuhu no miya-dukahe ni tuke te mo, hito no kokoro wo nomi 
ugokasi, urami wo ohu tumori ni ya ari kem, ito atusiku nari yuki, mono kokoro-
boso-ge ni sato-gati naru wo, iyo-iyo aka zu ahare naru mono ni omohosi te hito 
no sosiri wo mo e habakara se tamaha zu, yo no tamesi ni mo nari nu beki ohom-
motenasi nari.

Kamdatime, uhe-bito nado mo, ainaku me wo sobame tutu, "Ito mabayuki hito no 
ohom-oboye nari. Morokosi ni mo, kakaru koto no okori ni koso, yo mo midare, 
asikari kere" to, yau-yau amenosita ni mo adikinau, hito no mote-nayami-gusa ni 
nari te, Yauki-hi no tamesi mo hiki ide tu beku nariyuku ni, ito hasitanaki koto 
ohokare do, katazikenaki mi-kokoro-bahe no taguhi naki wo tanomi ni te mazirahi 
tamahu.

TiTi no Dainagon ha nakunari te haha Kita-no-kata nam inisihe no yosi aru ni te, 
oya uti-gusi, sasi-atari te yo no oboye hanayaka naru ohom-kata-gata ni mo itau 
otora zu, nani-goto no gisiki wo mo motenasi tamahi kere do, tori-tate te haka-
bakasiki usiro-mi si nakere ba, koto aru toki ha, naho yori-dokoro naku kokoro-
boso-ge nari.


Saki no yo ni mo ohom-tigiri ya hukakari kem, yo ni naku kiyora naru tama no 
wonoko miko sahe umare tamahi nu. Itusika to kokoro-motonagara se tamahi te, 
isogi mawirase te go-ran-zuru ni, meduraka naru tigo no ohom-katati nari.

Iti-no-Miko ha, Udaizin no Nyougo no ohom-hara ni te, yose omoku, utagahi naki 
Mauke-no-kimi to, yo ni mote-kasiduki kikoyure do, kono ohom-nihohi ni ha narabi 
tamahu beku mo ara zari kere ba, ohokata no yamgotonaki ohom-omohi ni te, kono 
Kimi wo ba, watakusi-mono ni omohosi kasiduki tamahu koto kagiri nasi.

Hazime yori osinabete no uhe-miya-dukahe si tamahu beki kiha ni ha ara zari ki. 
Oboye ito yamgotonaku, zyauzu-mekasi kere do, warinaku matuhasa se tamahu amari 
ni, sarubeki ohom-asobi no wori-wori, nani-goto ni mo yuwe aru koto no husi-busi 
ni ha, madu mau-nobora se tamahu. Aru-toki ni ha ohotono-gomori sugusi te, 
yagate saburahase tamahi nado, anagati ni o-mahe sara zu mote-nasa se tamahi si 
hodo ni, onodukara karoki kata ni mo miye si wo, kono Miko umare tamahi te noti 
ha, ito kokoro koto ni omohosi oki te tare ba, Bau ni mo, you se zu ha, kono
Miko no wi tamahu beki na'meri to, Ichi-no-Miko no Nyougo ha obosi utagahe ri. 
Hito yori saki ni mawiri tamahi te, yamgotonaki ohom-omohi nabete nara zu, Miko-
tati nado mo ohasimase ba, kono Ohom-kata no ohom-isame wo nomi zo, naho 
wadurahasiu kokoro-gurusiu omohi kikoye sase tamahi keru.
 
Kasikoki mi-kage wo ba tanomi kikoye nagara, otosime kizu wo motome tamahu hito 
ha ohoku, waga mi ha ka-yowaku mono-hakanaki arisama ni te, naka-naka naru mono-
omohi wo zo si tamahu. Mi-tubone ha Kiritubo nari. Amata no ohom-Kata-gata wo 
sugi sase tamahi te, hima naki o-mahe-watari ni, hito no mi-kokoro wo tukusi 
tamahu mo, geni kotowari to miye tari. Mau-nobori tamahu ni mo, amari uti-sikiru 
wori-wori ha, uti-hasi, wata-dono no koko kasiko no miti ni, ayasiki waza wo si 
tutu, ohom-okuri mukahe no hito no kinu no suso, tahe gataku, masanaki koto mo 
ari. Mata aru toki ni ha, e sara nu me-dau no to wo sasi-kome, konata kanata 
kokoro wo ahase te, hasitaname wadurahase tamahu toki mo ohokari. Koto ni hure 
te kazu sira zu kurusiki koto nomi masare ba, ito itau omohi wabi taru wo, itodo 
ahare to go-ran-zi te, Kourau-den ni motoyori saburahi tamahu Kaui no zausi wo 
hoka ni utusa se tamahi te, Uhe-tubone ni tamaha su. Sono urami masite yara m 
kata nasi.
'''

    
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


def main():
    f = TextMarkovFrequencies(string.ascii_lowercase, japanese.lower())
    print ''.join(itertools.islice(f.make_chain('a'), 14))

if __name__ == '__main__':
    main()

