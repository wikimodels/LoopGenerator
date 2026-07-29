import random
import math
from .core import *
def gen_jazz(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    notes = []
    scale = "dorian" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def map_jazz_quality(deg):
        return extend_dominant(diatonic_seventh(scale, deg))
    prog = [(deg, map_jazz_quality(deg)) for deg in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps
    scale_len = len(SCALES[scale])

    prev_comp = None
    prev_mel_val = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar*bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        comp_intervals = maybe_add_color(shell_intervals(qual), prob=0.2)
        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=3)
        comp_names = realize(comp_pitches)
        prev_comp = comp_pitches

        next_bar = (bar+1) % num_bars
        next_deg = prog[next_bar % n][0]
        next_root_pc = key_pc + SCALES[scale][next_deg % len(SCALES[scale])]

        # FIX #6: genuine stepwise walking bass for ANY beats_per_bar. The old
        # version padded beats beyond the 4th with repeats of the bare 5th,
        # so e.g. a 6/4 bar walked root-3rd-5th-5th-5th-approach. Now every
        # interior beat takes the next scale degree up from the root, and
        # only the very last beat is the chromatic approach into the next chord.
        walk = []
        for b in range(beats_per_bar):
            if b == 0:
                walk.append(root_pc)
            elif b == beats_per_bar - 1 and beats_per_bar > 1:
                walk.append(next_root_pc - 1)
            else:
                walk.append(key_pc + SCALES[scale][(deg + b) % scale_len])
        for b,pc_ in enumerate(walk):
            notes.append(mk(s0+b*4, note_name(pc_,2), "4n", 0.6+0.05*(b==0), steps))

        # FIX #7: comping now hits the off-beat ("and") of every beat except
        # the first, for ANY beats_per_bar — not just the two hardcoded cases
        # (4 and 5) from before.
        comp_beats = [b + 0.5 for b in range(1, beats_per_bar)]
        for b_idx in comp_beats:
            off = int(b_idx * 4)
            if s0 + off < s0 + bar_steps:
                for note in comp_names:
                    notes.append(mk(s0+off, note, "8n", 0.35, steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = (0,1,2,3) if len(mel_chord)>3 else (0,1,2)
        mel_notes_cnt = int(beats_per_bar * 1.5)
        mel_idx = contour_sequence(mel_notes_cnt, choices=mel_choices, start=carry_start(mel_choices, prev_mel_val))
        for i,ci in enumerate(mel_idx):
            step = s0 + 2 + i*2
            if step >= s0+bar_steps: continue
            note = mel_chord[ci % len(mel_chord)]
            notes.append(mk(step, note, "8n", 0.5+random.uniform(0,0.15), steps))
        prev_mel_val = mel_idx[-1]

        if bar % n == 1:
            blue = note_name(root_pc+3, 5)
            blue_step = s0 + min(10, bar_steps - 2)
            notes.append(mk(blue_step, blue, "16n", 0.55, steps))
    return notes

def gen_blues(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "blues"

    degrees = generate_harmony("major", length=4)
    prog = [(d, "dom7") for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_comp = None
    prev_mel = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps

        root_pc = key_pc + SCALES["major"][deg]

        # FIX #13: this used to play bass_pattern[b%4] TWICE per beat (same
        # pitch at the beat and at its "and"), which just stutters one note
        # instead of walking. It's now indexed per EIGHTH NOTE, so the
        # classic root-5th-6th-5th boogie pattern actually moves at the
        # eighth-note rate it was written for.
        bass_pattern = [0, 7, 9, 7]
        for e in range(beats_per_bar * 2):
            p_idx = e % len(bass_pattern)
            step = s0 + e * 2
            vel = 0.75 if e == 0 else (0.7 if e % 2 == 0 else 0.5)
            notes.append(mk(step, note_name(root_pc + bass_pattern[p_idx], 2), "8n", vel, steps))

        comp_intervals = shell_intervals(qual)
        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=3)
        for b in range(beats_per_bar):
            if b % 2 == 1:
                off = b * 4 + 2
                for note in realize(comp_pitches):
                    notes.append(mk(s0 + off, note, "8n", 0.4, steps))
        prev_comp = comp_pitches

        mel_choices = (0, 1, 2, 3, 4, 5)
        start = carry_start(mel_choices, prev_mel)
        mel_cnt = beats_per_bar * 2
        mel_contour = contour_sequence(mel_cnt, choices=mel_choices, start=start, reversal_bias=0.45)
        for i, ci in enumerate(mel_contour):
            step = s0 + i * 2
            if random.random() < 0.7:
                notes.append(mk(step, note_name(key_pc + SCALES["blues"][ci], 5), "8n", 0.6 + random.uniform(0,0.1), steps))
        prev_mel = mel_contour[-1]

    return notes

def gen_ragtime(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    degrees = generate_harmony(scale, length=4)
    def map_ragtime(d):
        return "dom7" if d in (1,4,5,6) else ("min" if d in (2,) else "maj")
    prog = [(d, map_ragtime(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None

    # FIX #8: the syncopation was a hardcoded 16-step pattern [0,3,6,8,11,14].
    # It's now expressed as fractions of the bar and rescaled to bar_steps,
    # so it still lands on the same syncopated feel at any beats_per_bar
    # instead of clipping (smaller bars) or leaving the tail of the bar
    # empty (larger bars).
    rhythm_fracs = [0/16, 3/16, 6/16, 8/16, 11/16, 14/16]

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        chord_ivs = CHORD_QUALITIES[qual]
        chord_notes = [note_name(root_pc + iv, 3) for iv in chord_ivs]

        for b in range(beats_per_bar):
            if b % 2 == 0:
                bass_note = note_name(root_pc + (chord_ivs[0] if b % 4 == 0 else chord_ivs[2 % len(chord_ivs)]), 2)
                notes.append(mk(s0 + b * 4, bass_note, "8n", 0.7, steps))
            else:
                for cn in chord_notes:
                    notes.append(mk(s0 + b * 4, cn, "8n", 0.5, steps))

        mel_choices = (0, 1, 2, 4, 5)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start)

        rhythm_pattern = sorted(set(int(round(f * bar_steps)) for f in rhythm_fracs))
        rhythm_pattern = [r for r in rhythm_pattern if r < bar_steps]
        for r_step in rhythm_pattern:
            ci = mel_contour[r_step % len(mel_contour)]
            notes.append(mk(s0 + r_step, scale_tone(key_pc, scale, deg + ci, 5), "8n", 0.65, steps))
        prev_mel = mel_contour[-1]

    return notes

def gen_bossa_nova(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    degrees = generate_harmony(scale, length=4)
    def map_bossa(d):
        return {0:"maj9", 1:"min9", 2:"min7", 3:"maj9", 4:"dom9", 5:"min7", 6:"m7b5"}.get(d, "maj9")
    prog = [(d, map_bossa(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.7, steps))
        ivs = CHORD_QUALITIES[qual]

        if beats_per_bar >= 3:
            half_bar = (beats_per_bar // 2) * 4
            notes.append(mk(s0 + half_bar - 1, note_name(root_pc + ivs[2], 2), "16n", 0.5, steps))
            notes.append(mk(s0 + half_bar, note_name(root_pc + ivs[2], 2), "4n", 0.6, steps))

        comp_names = []
        if len(ivs) >= 4:
            comp_names.append(note_name(root_pc + ivs[1], 3))
            comp_names.append(note_name(root_pc + ivs[2], 3))
            comp_names.append(note_name(root_pc + ivs[3], 3))
            if len(ivs) > 4:
                comp_names.append(note_name(root_pc + ivs[4], 3))
        else:
            comp_names = [note_name(root_pc + iv, 3) for iv in ivs]

        comp_steps = []
        c = 0 if random.random() < 0.5 else 1
        while c < bar_steps:
            comp_steps.append(c)
            c += 3 if (len(comp_steps) % 2 != 0) else 4

        for c_step in comp_steps:
            for note in comp_names:
                notes.append(mk(s0 + c_step, note, "8n", 0.45 + random.uniform(0, 0.1), steps))

        # FIX: The global chord_tones() function now naturally folds extensions
        # into the same octave and sorts them. This prevents both octave jumps
        # (shrieking 9ths) AND contour inversions (due to unsorted arrays).
        mel_chord = chord_tones(root_pc, qual, 5)

        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps // 2, choices=mel_choices, start=start, reversal_bias=0.3)

        mel_steps = [s for s in range(2, bar_steps, 3)]
        for m_idx, m_step in enumerate(mel_steps):
            if random.random() < 0.7:
                ci = mel_contour[m_idx % len(mel_contour)]
                notes.append(mk(s0 + m_step, mel_chord[ci], "8n", 0.6 + random.uniform(0, 0.1), steps))

        prev_mel = mel_contour[-1]

    return notes

def gen_neo_soul(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    degrees = generate_harmony(scale, length=4)
    def map_neo_soul(d):
        return {0:"maj9", 1:"min9", 2:"min9", 3:"maj9", 4:"dom13", 5:"min9", 6:"m7b5"}.get(d, "maj9")
    prog = [(d, map_neo_soul(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_comp = None
    prev_mel = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps

        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        if deg == 0 and qual == "dim7":
            root_pc += 1

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.65, steps))
        if beats_per_bar >= 4:
            notes.append(mk(s0 + 8, note_name(root_pc, 2), "4n", 0.5, steps))

        ivs = CHORD_QUALITIES[qual]
        comp_intervals = [ivs[1], ivs[3]] if len(ivs) >= 4 else [ivs[1], ivs[2]]
        if len(ivs) > 4: comp_intervals.append(ivs[4])
        if len(ivs) > 5: comp_intervals.append(ivs[5])

        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=4)
        comp_names = realize(comp_pitches)
        prev_comp = comp_pitches

        hits = [0]
        for b in range(1, beats_per_bar):
            if random.random() < 0.7:
                hits.append(b * 4 + random.choice([0, 1]))

        for h in hits:
            if h < bar_steps and random.random() < 0.8:
                vel = 0.5 if h in (0, 8) else 0.4
                for note in comp_names:
                    notes.append(mk(s0 + h, note, "8n", vel + random.uniform(0, 0.05), steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start, reversal_bias=0.4)

        for m_step in range(bar_steps):
            if random.random() < 0.3:
                ci = mel_contour[m_step % len(mel_contour)]
                target_note = mel_chord[ci]

                if random.random() < 0.4:
                    target_pc = root_pc + ivs[ci % len(ivs)]
                    grace = note_name(target_pc - 1, 5)
                    # FIX #2: grace note used to sit at a fractional step
                    # (m_step - 0.25). Now placed one integer step earlier,
                    # clamped so it can't go negative.
                    grace_step = max(0, s0 + m_step - 1)
                    notes.append(mk(grace_step, grace, "32n", 0.4, steps))

                notes.append(mk(s0 + m_step, target_note, "16n", 0.65 + random.uniform(0, 0.1), steps))

        prev_mel = mel_contour[-1]

    return notes

