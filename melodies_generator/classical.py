import random
import math
from .core import *

def _quality_for(scale, entry, qual_map=None):
    """Resolve a harmony entry (dict from generate_harmony) to a chord quality,
    honoring explicit overrides (secondary dominants / borrowed chords) before
    falling back to a genre's own degree->quality map."""
    if entry["quality"] is not None and entry["quality"] in CHORD_QUALITIES:
        return entry["quality"]
    if qual_map is not None:
        return qual_map.get(entry["degree"] % 7, "maj")
    return diatonic_quality(scale, entry["degree"])

def _root_pc(key_pc, scale, entry):
    deg = entry["degree"]
    return key_pc + SCALES[scale][deg % len(SCALES[scale])]


# ---------------------------------------------------------------------------
# NEOCLASSICAL
# ---------------------------------------------------------------------------

NEOCLASSICAL_MINOR = {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim"}
NEOCLASSICAL_MAJOR = {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}

def gen_neoclassical(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    notes = []
    scale = random.choice(["harmonic_minor", "melodic_minor_asc"]) if minor else random.choice(["major", "lydian"])
    length = random.choice([4, 4, 8])
    prog = generate_harmony(scale, length=length, detailed=True)
    qual_map = NEOCLASSICAL_MINOR if minor else NEOCLASSICAL_MAJOR
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    arp_notes_per_bar = random.choice([beats_per_bar, beats_per_bar * 2, beats_per_bar * 3])
    step_span = max(1, bar_steps // arp_notes_per_bar)
    arp_dur = SPAN_TO_DURATION.get(step_span, "16n")
    arp_direction = random.choice(["asc", "desc", "free"])

    prev_arp_val = None
    prev_mel_val = None

    for bar in range(num_bars):
        entry = prog[bar % n]
        deg = entry["degree"]
        qual = _quality_for(scale, entry, qual_map)
        bar_start = bar * bar_steps
        root_pc = _root_pc(key_pc, scale, entry)
        chord = chord_tones(root_pc, qual, 3) + [note_name(root_pc, 4)]

        notes.append(mk(bar_start, note_name(root_pc, 2), "1n", 0.6 + random.uniform(0, 0.1), steps))

        arp_choices = tuple(range(len(chord)))
        if arp_direction == "asc":
            start_idx = 0
        elif arp_direction == "desc":
            start_idx = len(arp_choices) - 1
        else:
            start_idx = carry_start(arp_choices, prev_arp_val)
        bias = 0.15 if arp_direction in ("asc", "desc") else random.uniform(0.35, 0.6)
        arp_idx = contour_sequence(arp_notes_per_bar, choices=arp_choices, start=start_idx,
                                    reversal_bias=bias, leap_prob=0.2)
        for i, ci in enumerate(arp_idx):
            note = chord[ci]
            notes.append(mk(bar_start + i*step_span, note, arp_dur, 0.35+random.uniform(0,0.2), steps))
        prev_arp_val = arp_idx[-1]

        mel_choices = (deg, deg+2, deg+4, deg+6, deg+1, deg+3)
        mel_hits = random.choice([2, 2, 3])
        mel_contour = contour_sequence(mel_hits, choices=mel_choices,
                                        start=carry_start(mel_choices, prev_mel_val),
                                        leap_prob=0.25)
        offsets = sorted(random.sample(range(int(bar_steps*0.25), bar_steps), k=min(mel_hits, bar_steps)))
        for i, off in enumerate(offsets):
            notes.append(mk(bar_start+off, scale_tone(key_pc, scale, mel_contour[i % len(mel_contour)], 5),
                             random.choice(["4n", "8n"]), 0.65 - 0.05*i, steps))
        prev_mel_val = mel_contour[-1]
    return notes


# ---------------------------------------------------------------------------
# CLASSICAL ALBERTI
# ---------------------------------------------------------------------------

def gen_classical_alberti(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = random.choice(["major", "major", "mixolydian"])
    length = random.choice([4, 4, 8])
    prog = generate_harmony(scale, length=length, detailed=True)
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    alberti_patterns = [[0,2,1,2],[0,1,2,1],[0,2,1,3],[0,1,2,3]]
    mel_choices = (0,1,2,3,4,5,6,7)
    prev_mel_val = None

    for bar in range(num_bars):
        local_bar = bar % n
        entry = prog[local_bar]
        deg = entry["degree"]
        qual = _quality_for(scale, entry)
        s0 = bar*bar_steps
        root_pc = _root_pc(key_pc, scale, entry)
        triad = chord_tones(root_pc, qual, 3)

        # pick alberti pattern per bar (varies more than one fixed pattern for the whole piece)
        alberti_order = random.choice(alberti_patterns)
        pattern_len = len(alberti_order)
        for i in range(beats_per_bar * 2):
            step = s0+i*2
            idx = alberti_order[i % pattern_len] % len(triad)
            note = triad[idx]
            notes.append(mk(step, note, "8n", 0.4 + random.uniform(0, 0.1), steps))

        start = carry_start(mel_choices, prev_mel_val)
        phrase = contour_sequence(beats_per_bar, choices=mel_choices, start=start,
                                   reversal_bias=random.uniform(0.35, 0.55), max_run=3, leap_prob=0.15)
        if local_bar == n-1:
            phrase = phrase[:-1] + [0]
        for i,d in enumerate(phrase):
            notes.append(mk(s0+i*4, scale_tone(key_pc,scale,deg+d,5), "4n", 0.7-0.05*i, steps))
        prev_mel_val = phrase[-1]

        if local_bar==n-1 and bar_steps >= 4 and random.random() < 0.8:
            trill_notes = random.choice([(2,0), (1,-1), (3,1)])
            for k in range(4):
                notes.append(mk(s0 + bar_steps - 4 + k, scale_tone(key_pc,scale, trill_notes[k%2],6), "32n", 0.55, steps))
    return notes


# ---------------------------------------------------------------------------
# WALTZ
# ---------------------------------------------------------------------------

WALTZ_MINOR = {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim"}
WALTZ_MAJOR = {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"dom7", 5:"min", 6:"dim"}

def gen_waltz(key_pc, scale_name, bpm, steps, beats_per_bar=3, minor=False):
    """Takes an explicit `minor` flag instead of flipping a coin on its own
    scale. Defaults to beats_per_bar=3 — a waltz that isn't in 3 isn't a waltz."""
    notes = []
    scale = "harmonic_minor" if minor else "major"
    length = random.choice([4, 4, 6])
    prog = generate_harmony(scale, length=length, detailed=True)
    qual_map = WALTZ_MINOR if minor else WALTZ_MAJOR
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None
    prev_pad = None
    # some bars use "oom-pah-pah", others a fuller pad on every beat — varies per phrase
    accompaniment_style = random.choice(["oom_pah_pah", "sustained_pad", "broken"])

    for bar in range(num_bars):
        entry = prog[bar % n]
        deg = entry["degree"]
        qual = _quality_for(scale, entry, qual_map)
        s0 = bar * bar_steps
        root_pc = _root_pc(key_pc, scale, entry)

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.6 + random.uniform(0, 0.1), steps))

        pad_intervals = maybe_add_color(CHORD_QUALITIES.get(qual, CHORD_QUALITIES["maj"]), prob=0.2)
        pad_pitches = voice_lead(pad_intervals, root_pc, prev_pad, anchor_octave=4, jump_prob=0.08)

        if accompaniment_style == "oom_pah_pah":
            for b in range(1, beats_per_bar):
                for note in realize(pad_pitches):
                    notes.append(mk(s0 + b * 4, note, "4n", 0.4, steps))
        elif accompaniment_style == "sustained_pad":
            for note in realize(pad_pitches):
                notes.append(mk(s0 + 4, note, "2n.", 0.35, steps))
        else:  # broken: staggered entries instead of all voices together
            for vi, note in enumerate(realize(pad_pitches)):
                beat = 1 + (vi % (beats_per_bar - 1))
                notes.append(mk(s0 + beat * 4, note, "4n", 0.4, steps))
        prev_pad = pad_pitches

        mel_choices = (0, 1, 2, 3, 4, 5, 6, 7)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(beats_per_bar * 2, choices=mel_choices, start=start,
                                        reversal_bias=random.uniform(0.2, 0.4), max_run=4, leap_prob=0.2)
        note_prob = random.uniform(0.65, 0.9)
        for i, ci in enumerate(mel_contour):
            step = s0 + i * 2
            if random.random() < note_prob:
                notes.append(mk(step, scale_tone(key_pc, scale, deg + ci, 5), "8n",
                                 0.55 + random.uniform(0, 0.1), steps))
        prev_mel = mel_contour[-1]

    return notes


# ---------------------------------------------------------------------------
# ROMANTIC
# ---------------------------------------------------------------------------

ROMANTIC_MINOR = {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim7"}
ROMANTIC_MAJOR = {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"dom7", 5:"min", 6:"dim"}

def gen_romantic(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """Takes an explicit `minor` flag instead of rolling its own scale choice
    independent of what was requested."""
    notes = []
    scale = random.choice(["harmonic_minor", "natural_minor"]) if minor else random.choice(["major", "lydian"])
    length = random.choice([4, 4, 8])
    prog = generate_harmony(scale, length=length, detailed=True)
    qual_map = ROMANTIC_MINOR if minor else ROMANTIC_MAJOR
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None
    arp_shape = random.choice(["classic", "wide", "cascading"])

    for bar in range(num_bars):
        entry = prog[bar % n]
        deg = entry["degree"]
        qual = _quality_for(scale, entry, qual_map)
        s0 = bar * bar_steps
        root_pc = _root_pc(key_pc, scale, entry)

        ivs = CHORD_QUALITIES.get(qual, CHORD_QUALITIES["min"])
        third = ivs[1] if len(ivs) > 1 else 3
        fifth = ivs[2] if len(ivs) > 2 else 7

        if arp_shape == "classic":
            arp_pitches = [root_pc - 12, root_pc - 12 + fifth, root_pc + third]
            pattern = [arp_pitches[0], arp_pitches[1], arp_pitches[2], arp_pitches[1]]
        elif arp_shape == "wide":
            arp_pitches = [root_pc - 12, root_pc + third, root_pc + fifth, root_pc + 12]
            pattern = arp_pitches
        else:  # cascading
            arp_pitches = [root_pc + 12, root_pc + fifth, root_pc + third, root_pc]
            pattern = arp_pitches

        for i in range(beats_per_bar * 2):
            step = s0 + i * 2
            p_idx = i % len(pattern)
            notes.append(mk(step, note_name(pattern[p_idx], 3), "8n", 0.45 + 0.05 * (i % 2 == 0), steps))

        mel_choices = (0, 1, 2, 3, 4, 5, 6, 7)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(beats_per_bar * 2, choices=mel_choices, start=start,
                                        reversal_bias=random.uniform(0.2, 0.4), max_run=3, leap_prob=0.2)

        note_prob = random.uniform(0.65, 0.85)
        for i, ci in enumerate(mel_contour):
            if random.random() < note_prob:
                # Rubato is rounded to the nearest int step before mk() ever
                # sees it, and clamped in-range — never leaks a float step.
                base_step = s0 + i * 2
                rubato = random.uniform(-0.3, 0.4)
                final_step = max(0, min(steps - 1, base_step + rubato))
                notes.append(mk(int(round(final_step)), scale_tone(key_pc, scale, deg + ci, 5), "8n",
                                 0.6 + random.uniform(0, 0.15), steps))

        prev_mel = mel_contour[-1]

    return notes
