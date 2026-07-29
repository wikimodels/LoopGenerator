import random
import math
from .core import *
def gen_modal_folk(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "dorian"
    degrees = generate_harmony(scale, length=4)
    prog = degrees
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    mel_choices = (0,1,2,3,4,5)
    prev_pad = None
    prev_mel_val = None

    for bar in range(num_bars):
        deg = prog[bar % n]
        s0 = bar*bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        notes.append(mk(s0, note_name(key_pc,2), "1n", 0.5, steps))

        qual = diatonic_quality(scale, deg)
        pad_pitches = voice_lead(CHORD_QUALITIES[qual], root_pc, prev_pad, anchor_octave=4)
        for note in realize(pad_pitches):
            notes.append(mk(s0 + bar_steps//2, note, "2n", 0.3, steps))
        prev_pad = pad_pitches

        start = carry_start(mel_choices, prev_mel_val)
        mel_cnt = beats_per_bar * 3
        mel_contour = contour_sequence(mel_cnt, choices=mel_choices, start=start, reversal_bias=0.4, max_run=3)
        for i,d in enumerate(mel_contour):
            step = s0 + i
            if step>=s0+bar_steps: break
            notes.append(mk(step, scale_tone(key_pc,scale,deg+d,5), "8n", 0.5+random.uniform(0,0.15), steps))
        prev_mel_val = mel_contour[-1]

        grace_step = s0 + max(0, bar_steps - 2)
        notes.append(mk(grace_step, scale_tone(key_pc,scale,deg+1,5), "32n", 0.4, steps))
    return notes

def gen_lofi(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    degrees = generate_harmony(scale, length=4)
    def map_lofi(d):
        return {0:"maj9", 1:"min9", 2:"min7", 3:"maj9", 4:"dom9", 5:"min7", 6:"m7b5"}.get(d, "maj9")
    prog = [(d, map_lofi(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_comp = None
    prev_mel = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps

        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.6, steps))

        ivs = CHORD_QUALITIES[qual] if qual in CHORD_QUALITIES else CHORD_QUALITIES["min7"]
        comp_intervals = [ivs[1], ivs[3]] if len(ivs) >= 4 else [ivs[1], ivs[2]]
        if len(ivs) > 4: comp_intervals.append(ivs[4])

        if random.random() < 0.5:
            if qual in ("min9", "min7"): comp_intervals.append(17)
            elif qual in ("maj9", "maj7"): comp_intervals.append(14)

        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=4)
        comp_names = realize(comp_pitches)
        prev_comp = comp_pitches

        hits = [0]
        if random.random() < 0.7:
            second_hit = int(bar_steps * 0.5) + (2 if random.random() < 0.5 else -2)
            if 0 < second_hit < bar_steps:
                hits.append(second_hit)

        for h in hits:
            if h < bar_steps:
                if h > 0:
                    notes.append(mk(s0 + h, note_name(root_pc, 2), "8n", 0.45, steps))
                for idx, note in enumerate(comp_names):
                    # FIX #2: strum offset used to be a fractional step
                    # (idx*0.12) fed straight into mk(). Now rounded to int.
                    strum_step = s0 + h + int(round(idx * 0.12))
                    notes.append(mk(strum_step, note, "4n", 0.45 - idx * 0.05, steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps // 2, choices=mel_choices, start=start, reversal_bias=0.2)

        mel_steps = [s for s in range(2, bar_steps, 3)]
        for m_idx, m_step in enumerate(mel_steps):
            if random.random() < 0.6:
                ci = mel_contour[m_idx % len(mel_contour)]
                notes.append(mk(s0 + m_step, mel_chord[ci], "8n", 0.6 + random.uniform(0, 0.1), steps))

        prev_mel = mel_contour[-1]

    return notes

def gen_video_game(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    degrees = generate_harmony(scale, length=4)
    def map_vg(d):
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")
    prog = [(d, map_vg(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        ivs = CHORD_QUALITIES[qual]

        for i in range(bar_steps):
            if i % 2 == 0:
                octave = 2 if (i % 4 == 0) else 3
                notes.append(mk(s0 + i, note_name(root_pc, octave), "16n", 0.7, steps))

        arp_pattern = [root_pc + ivs[0], root_pc + ivs[1], root_pc + ivs[2], root_pc + ivs[1]]
        for i in range(bar_steps):
            p_idx = i % len(arp_pattern)
            notes.append(mk(s0 + i, note_name(arp_pattern[p_idx], 4), "16n", 0.45, steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start, reversal_bias=0.5, max_run=4)

        for m_idx, m_step in enumerate(range(bar_steps)):
            prob = 0.8 if m_step % 2 == 0 else 0.3
            if random.random() < prob:
                ci = mel_contour[m_idx % len(mel_contour)]
                notes.append(mk(s0 + m_step, mel_chord[ci], "16n", 0.85, steps))

        prev_mel = mel_contour[-1]

    return notes

