import random
import math
from .core import *
def gen_neoclassical(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    notes = []
    scale = "harmonic_minor" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def get_qual(d):
        if minor:
            return {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")
    qualities = [get_qual(d) for d in degrees]
    n = len(degrees)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    arp_notes_per_bar = random.choice([beats_per_bar, beats_per_bar * 2])
    step_span = max(1, bar_steps // arp_notes_per_bar)
    arp_dur = SPAN_TO_DURATION[step_span] if step_span in SPAN_TO_DURATION else "16n"

    prev_arp_val = None
    prev_mel_val = None

    for bar in range(num_bars):
        deg, qual = degrees[bar % n], qualities[bar % n]
        bar_start = bar*bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        chord = chord_tones(root_pc, qual, 3) + [note_name(root_pc,4)]
        notes.append(mk(bar_start, note_name(root_pc,2), "1n", 0.65, steps))

        arp_choices = tuple(range(len(chord)))
        arp_idx = contour_sequence(arp_notes_per_bar, choices=arp_choices,
                                    start=carry_start(arp_choices, prev_arp_val))
        for i,ci in enumerate(arp_idx):
            note = chord[ci]
            notes.append(mk(bar_start+i*step_span, note, arp_dur, 0.35+random.uniform(0,0.2), steps))
        prev_arp_val = arp_idx[-1]

        mel_choices = (deg, deg+2, deg+4, deg+6, deg+1)
        mel_contour = contour_sequence(2, choices=mel_choices,
                                       start=carry_start(mel_choices, prev_mel_val))
        beat_offset1 = int(bar_steps * 0.375)
        beat_offset2 = int(bar_steps * 0.75)
        notes.append(mk(bar_start+beat_offset1, scale_tone(key_pc, scale, mel_contour[0], 5), "4n", 0.65, steps))
        notes.append(mk(bar_start+beat_offset2, scale_tone(key_pc, scale, mel_contour[1], 5), "4n", 0.55, steps))
        prev_mel_val = mel_contour[-1]
    return notes

def gen_classical_alberti(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    degrees = generate_harmony(scale, length=4)
    prog = degrees
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    alberti_order = random.choice([[0,2,1,2],[0,1,2,1]])
    mel_choices = (0,1,2,3,4,5,6,7)
    prev_mel_val = None

    for bar in range(num_bars):
        local_bar = bar % n
        deg = prog[local_bar]
        qual = diatonic_quality(scale, deg)
        s0 = bar*bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        triad = chord_tones(root_pc, qual, 3)

        for i in range(beats_per_bar * 2):
            step = s0+i*2
            note = triad[alberti_order[i%4]]
            notes.append(mk(step, note, "8n", 0.45, steps))

        start = carry_start(mel_choices, prev_mel_val)
        phrase = contour_sequence(beats_per_bar, choices=mel_choices, start=start, reversal_bias=0.45, max_run=3)
        if local_bar == n-1:
            phrase = phrase[:-1] + [0]
        for i,d in enumerate(phrase):
            notes.append(mk(s0+i*4, scale_tone(key_pc,scale,deg+d,5), "4n", 0.7-0.05*i, steps))
        prev_mel_val = phrase[-1]

        if local_bar==n-1 and bar_steps >= 4:
            for k in range(4):
                notes.append(mk(s0 + bar_steps - 4 + k, scale_tone(key_pc,scale, (2 if k%2==0 else 0),6), "32n", 0.55, steps))
    return notes

def gen_waltz(key_pc, scale_name, bpm, steps, beats_per_bar=3, minor=False):
    """FIX #3 & #4: takes an explicit `minor` flag instead of flipping a coin
    on its own scale (which used to silently ignore whatever scale the
    caller/style metadata actually specified). Also now defaults to
    beats_per_bar=3 — a waltz that isn't in 3 isn't a waltz."""
    notes = []
    scale = "harmonic_minor" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def map_waltz(d):
        if minor:
            return {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"dom7", 5:"min", 6:"dim"}.get(d, "maj")
    prog = [(d, map_waltz(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None
    prev_pad = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.65, steps))

        pad_pitches = voice_lead(CHORD_QUALITIES[qual], root_pc, prev_pad, anchor_octave=4)
        for b in range(1, beats_per_bar):
            for note in realize(pad_pitches):
                notes.append(mk(s0 + b * 4, note, "4n", 0.45, steps))
        prev_pad = pad_pitches

        mel_choices = (0, 1, 2, 3, 4, 5, 6, 7)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(beats_per_bar * 2, choices=mel_choices, start=start, reversal_bias=0.3, max_run=4)
        for i, ci in enumerate(mel_contour):
            step = s0 + i * 2
            if random.random() < 0.8:
                notes.append(mk(step, scale_tone(key_pc, scale, deg + ci, 5), "8n", 0.6, steps))
        prev_mel = mel_contour[-1]

    return notes

def gen_romantic(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """FIX #3: takes an explicit `minor` flag instead of rolling its own
    scale choice (60% harmonic_minor) independent of what was requested."""
    notes = []
    scale = "harmonic_minor" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def map_romantic(d):
        if minor:
            return {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim7"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"dom7", 5:"min", 6:"dim"}.get(d, "maj")
    prog = [(d, map_romantic(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        ivs = CHORD_QUALITIES[qual]
        arp_pitches = [
            root_pc - 12,
            root_pc - 12 + ivs[2],
            root_pc + ivs[1]
        ]

        pattern = [arp_pitches[0], arp_pitches[1], arp_pitches[2], arp_pitches[1]]
        for i in range(beats_per_bar * 2):
            step = s0 + i * 2
            p_idx = i % len(pattern)
            notes.append(mk(step, note_name(pattern[p_idx], 3), "8n", 0.45 + 0.05 * (i % 2 == 0), steps))

        mel_choices = (0, 1, 2, 3, 4, 5, 6, 7)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(beats_per_bar * 2, choices=mel_choices, start=start, reversal_bias=0.3, max_run=3)

        for i, ci in enumerate(mel_contour):
            if random.random() < 0.75:
                # FIX #2: rubato used to leak a rounded FLOAT step (e.g. 4.12)
                # straight into the JSON. It's now rounded to the nearest
                # integer step before mk() ever sees it, and clamped in-range.
                base_step = s0 + i * 2
                rubato = random.uniform(-0.25, 0.35)
                final_step = base_step + rubato
                final_step = max(0, min(steps - 1, final_step))
                notes.append(mk(int(round(final_step)), scale_tone(key_pc, scale, deg + ci, 5), "8n", 0.6 + random.uniform(0, 0.15), steps))

        prev_mel = mel_contour[-1]

    return notes

