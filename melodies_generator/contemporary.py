import random
import math
from .core import *

# ---------------------------------------------------------------------------
# helpers shared across genres
# ---------------------------------------------------------------------------

def _quality_for(scale, entry):
    """Resolve a harmony entry (dict from generate_harmony) to a chord quality
    string, honoring explicit overrides (secondary dominants / borrowed chords)."""
    if entry["quality"] is not None:
        return entry["quality"]
    return diatonic_quality(scale, entry["degree"])

def _root_pc(key_pc, scale, entry):
    deg = entry["degree"]
    return key_pc + SCALES[scale][deg % len(SCALES[scale])]


# ---------------------------------------------------------------------------
# MODAL FOLK
# ---------------------------------------------------------------------------

def gen_modal_folk(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = random.choice(["dorian", "phrygian", "mixolydian", "aeolian" if "aeolian" in SCALES else "natural_minor"])
    length = random.choice([4, 4, 6, 8])
    prog = generate_harmony(scale, length=length, detailed=True)
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    mel_choices = (0,1,2,3,4,5,6)
    prev_pad = None
    prev_mel_val = None
    drone_prob = random.uniform(0.5, 0.85)

    for bar in range(num_bars):
        entry = prog[bar % n]
        deg = entry["degree"]
        s0 = bar*bar_steps
        root_pc = _root_pc(key_pc, scale, entry)
        qual = _quality_for(scale, entry)

        # drone/root hit isn't guaranteed every bar anymore
        if random.random() < drone_prob:
            drone_oct = random.choice([1, 2])
            drone_dur = random.choice(["1n", "2n."])
            notes.append(mk(s0, note_name(key_pc, drone_oct), drone_dur, 0.5, steps))

        pad_intervals = maybe_add_color(CHORD_QUALITIES.get(qual, CHORD_QUALITIES["min"]), prob=0.3)
        pad_pitches = voice_lead(pad_intervals, root_pc, prev_pad, anchor_octave=4, jump_prob=0.1)
        pad_step = s0 + random.choice([bar_steps//2, bar_steps//4])
        for note in realize(pad_pitches):
            notes.append(mk(pad_step, note, random.choice(["2n", "4n."]), 0.28, steps))
        prev_pad = pad_pitches

        start = carry_start(mel_choices, prev_mel_val)
        mel_cnt = beats_per_bar * random.choice([2, 3, 4])
        mel_contour = contour_sequence(mel_cnt, choices=mel_choices, start=start,
                                        reversal_bias=random.uniform(0.3, 0.55), max_run=3,
                                        leap_prob=0.2)
        # scatter melody notes across the bar instead of a fixed 1-per-step run
        mel_step_positions = sorted(random.sample(range(bar_steps), k=min(mel_cnt, bar_steps)))
        for i, step in enumerate(mel_step_positions):
            d = mel_contour[i % len(mel_contour)]
            dur = random.choice(["8n", "8n", "16n", "8t"])
            notes.append(mk(s0 + step, scale_tone(key_pc, scale, deg + d, 5), dur,
                             0.5 + random.uniform(0, 0.2), steps))
        prev_mel_val = mel_contour[-1]

        if random.random() < 0.6:
            grace_step = s0 + max(0, bar_steps - random.choice([1, 2, 3]))
            grace_deg = deg + random.choice([1, -1, 2])
            notes.append(mk(grace_step, scale_tone(key_pc, scale, grace_deg, 5), "32n", 0.4, steps))

    return notes


# ---------------------------------------------------------------------------
# LOFI
# ---------------------------------------------------------------------------

LOFI_QUALITY_MAP = {0:"maj9", 1:"min9", 2:"min7", 3:"maj9", 4:"dom9", 5:"min7", 6:"m7b5"}
LOFI_QUALITY_ALT = {0:"maj7", 1:"min11", 2:"min9", 3:"maj7", 4:"dom7alt", 5:"min9", 6:"m7b5"}

def gen_lofi(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = random.choice(["major", "dorian", "mixolydian"])
    length = random.choice([4, 4, 6])
    prog = generate_harmony(scale, length=length, detailed=True)
    qual_map = random.choice([LOFI_QUALITY_MAP, LOFI_QUALITY_ALT])
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_comp = None
    prev_mel = None
    swing = random.choice([0, 1, 2])  # subtle step offset for a swung feel

    for bar in range(num_bars):
        entry = prog[bar % n]
        deg = entry["degree"]
        qual = entry["quality"] if entry["quality"] and entry["quality"] in CHORD_QUALITIES else qual_map.get(deg % 7, "maj9")
        s0 = bar * bar_steps
        root_pc = _root_pc(key_pc, scale, entry)

        notes.append(mk(s0, note_name(root_pc, 2), random.choice(["4n", "4n."]), 0.6, steps))

        ivs = CHORD_QUALITIES.get(qual, CHORD_QUALITIES["min7"])
        comp_intervals = [ivs[1], ivs[3]] if len(ivs) >= 4 else [ivs[1], ivs[2]]
        if len(ivs) > 4:
            comp_intervals.append(ivs[4])
        comp_intervals = maybe_add_color(comp_intervals, prob=0.4)

        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=4, jump_prob=0.1)
        comp_names = realize(comp_pitches)
        prev_comp = comp_pitches

        hits = [0]
        num_extra_hits = random.choices([0, 1, 2], weights=[30, 50, 20], k=1)[0]
        for _ in range(num_extra_hits):
            candidate = random.randint(2, bar_steps - 2)
            if candidate not in hits:
                hits.append(candidate)
        hits.sort()

        for h in hits:
            h_swung = h + (swing if h % 4 != 0 else 0)
            if h_swung < bar_steps:
                if h_swung > 0:
                    notes.append(mk(s0 + h_swung, note_name(root_pc, 2), "8n", 0.42, steps))
                for idx, note in enumerate(comp_names):
                    strum_step = s0 + h_swung + int(round(idx * random.choice([0, 0.1, 0.2])))
                    notes.append(mk(strum_step, note, random.choice(["4n", "4n."]),
                                     0.45 - idx * 0.05, steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps // 2, choices=mel_choices, start=start,
                                        reversal_bias=random.uniform(0.15, 0.35), leap_prob=0.2)

        step_gap = random.choice([3, 4, 5])
        offset = random.choice([1, 2, 3])
        mel_steps = [s for s in range(offset, bar_steps, step_gap)]
        hit_prob = random.uniform(0.45, 0.7)
        for m_idx, m_step in enumerate(mel_steps):
            if random.random() < hit_prob:
                ci = mel_contour[m_idx % len(mel_contour)]
                notes.append(mk(s0 + m_step, mel_chord[ci], random.choice(["8n", "8t"]),
                                 0.6 + random.uniform(0, 0.15), steps))

        prev_mel = mel_contour[-1] if mel_contour else prev_mel

    return notes


# ---------------------------------------------------------------------------
# VIDEO GAME
# ---------------------------------------------------------------------------

VG_QUALITY_MAP = {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}
VG_QUALITY_HEROIC = {0:"maj", 1:"min", 2:"min7", 3:"maj7", 4:"dom7", 5:"min", 6:"dim7"}

def gen_video_game(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = random.choice(["major", "lydian", "mixolydian"])
    length = random.choice([4, 8])
    prog = generate_harmony(scale, length=length, detailed=True)
    qual_map = random.choice([VG_QUALITY_MAP, VG_QUALITY_HEROIC])
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None
    # pick one of a few arp shapes per generation, not the same up-down-up every time
    arp_shape = random.choice(["updown", "up", "down", "updowndown"])

    for bar in range(num_bars):
        entry = prog[bar % n]
        deg = entry["degree"]
        qual = entry["quality"] if entry["quality"] and entry["quality"] in CHORD_QUALITIES else qual_map.get(deg % 7, "maj")
        s0 = bar * bar_steps
        root_pc = _root_pc(key_pc, scale, entry)

        ivs = CHORD_QUALITIES.get(qual, CHORD_QUALITIES["maj"])

        bass_pattern_choice = random.choice(["four_on_floor", "syncopated", "octave_bounce"])
        for i in range(bar_steps):
            hit = False
            octave = 2
            if bass_pattern_choice == "four_on_floor" and i % 4 == 0:
                hit = True
                octave = 2 if (i % 8 == 0) else 3
            elif bass_pattern_choice == "syncopated" and i % 4 in (0, 3):
                hit = True
                octave = 2
            elif bass_pattern_choice == "octave_bounce" and i % 2 == 0:
                hit = True
                octave = 2 if (i // 2) % 2 == 0 else 3
            if hit:
                notes.append(mk(s0 + i, note_name(root_pc, octave), "16n", 0.7, steps))

        base_arp = [root_pc + ivs[0], root_pc + ivs[1 % len(ivs)], root_pc + ivs[2 % len(ivs)]]
        if arp_shape == "updown":
            arp_pattern = base_arp + base_arp[::-1]
        elif arp_shape == "up":
            arp_pattern = base_arp + [root_pc + ivs[-1]]
        elif arp_shape == "down":
            arp_pattern = list(reversed(base_arp)) + [base_arp[0]]
        else:  # updowndown
            arp_pattern = base_arp + [base_arp[1], base_arp[0]]

        for i in range(bar_steps):
            p_idx = i % len(arp_pattern)
            if random.random() < 0.9:
                notes.append(mk(s0 + i, note_name(arp_pattern[p_idx], 4), "16n", 0.45, steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start,
                                        reversal_bias=random.uniform(0.4, 0.6), max_run=4,
                                        leap_prob=0.15)

        accent_pattern = random.choice([
            lambda s: 0.8 if s % 2 == 0 else 0.3,
            lambda s: 0.85 if s % 4 in (0, 3) else 0.25,
            lambda s: 0.9 if s % 3 == 0 else 0.35,
        ])
        for m_idx, m_step in enumerate(range(bar_steps)):
            prob = accent_pattern(m_step)
            if random.random() < prob:
                ci = mel_contour[m_idx % len(mel_contour)]
                notes.append(mk(s0 + m_step, mel_chord[ci], "16n", 0.85, steps))

        prev_mel = mel_contour[-1] if mel_contour else prev_mel

    return notes
