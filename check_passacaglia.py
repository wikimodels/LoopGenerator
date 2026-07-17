import sys, re
sys.stdout.reconfigure(encoding='utf-8')
from melodies_generator import generate_loop
from collections import defaultdict

loop = generate_loop('baroque_passacaglia', 'G#', bpm=100, steps=128, beats_per_bar=4, seed=479773)
notes = loop.get('notes', [])

def abs_pitch(note_str):
    """Returns absolute pitch in semitones (C0 = 0)."""
    m = re.match(r'([A-G]#?)(-?\d+)', note_str)
    if not m: return None
    names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    pc = names.index(m.group(1))
    octave = int(m.group(2))
    return pc + 12 * octave

# Intervals that are dissonant when played simultaneously in mid-low register:
# half step (1), whole step (2), tritone (6) — only when < 1 octave apart
# Major 7th (11), minor 7th (10) — dissonant below octave distance
DISS_CLOSE = {1, 2, 6, 10, 11}   # bad if within an octave
DISS_ANY   = {1, 2, 6}            # always bad

by_step = defaultdict(list)
for n in notes:
    by_step[n['step']].append(n)

print('=== INTERVAL ANALYSIS (absolute pitches) ===')
print('  (flags only intervals <13 semitones if dissonant, or always-bad ones)')
all_ok = True
for step in sorted(by_step.keys()):
    ns = by_step[step]
    bass_notes = [n for n in ns if n['note'][-1] == '2']
    block = [n for n in ns if n['duration'] == '2n']
    melody = [n for n in ns if n['duration'] == '4n' and n['note'][-1] in ('5','6')]

    if not bass_notes:
        continue
    b_abs = abs_pitch(bass_notes[0]['note'])
    bad = []
    chord_info = []
    for c in block:
        c_abs = abs_pitch(c['note'])
        if c_abs is None: continue
        real_iv = c_abs - b_abs   # always positive (chord above bass)
        iv_mod12 = real_iv % 12
        is_bad = (iv_mod12 in DISS_CLOSE and real_iv < 13) or (iv_mod12 in DISS_ANY)
        chord_info.append('%s(real+%d)' % (c['note'], real_iv))
        if is_bad:
            bad.append('%s(DISS real=%d)' % (c['note'], real_iv))
    flag = ' *** ' + ', '.join(bad) if bad else ' OK'
    if bad:
        all_ok = False
    print('step %3d: bass=%s, block=%s%s' % (step, bass_notes[0]['note'], chord_info, flag))

print()
print('RESULT:', 'ALL CONSONANT' if all_ok else 'STILL HAS DISSONANCE')
