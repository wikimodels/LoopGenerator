import random
import math
from .core import *

# =============================================================================
# SHARED HELPERS
# =============================================================================

def _build_degree_sequence(scale, num_bars, bars_per_phrase=8, chord_len=4):
    """
    Harmony that develops over long tracks instead of looping one 4-chord
    cell forever. A fresh `generate_harmony` call fires every
    `bars_per_phrase` bars, so short loops behave exactly as before while
    longer tracks get new phrase material every couple of loops — the jazz
    equivalent of moving from one chorus's changes into a fresh chorus
    rather than the identical 4-bar cell on repeat for the whole tune.
    """
    seq = []
    degrees = None
    for bar in range(num_bars):
        if bar % bars_per_phrase == 0:
            degrees = generate_harmony(scale, length=chord_len)
        seq.append(degrees[bar % chord_len])
    return seq


def _chorus_envelope(num_bars, chord_len=4):
    """
    Per-bar intensity 0..1 across choruses (one chorus = one pass through
    the `chord_len`-bar progression). Energy climbs through the middle
    choruses (comping thickens, blue notes/ornaments get more likely,
    melody density rises) and settles slightly on the final chorus, like an
    arrangement building through solos before an out-head. A tune with only
    one chorus stays at full intensity throughout.
    """
    num_choruses = max(1, math.ceil(num_bars / chord_len))
    env = []
    for bar in range(num_bars):
        ch = bar // chord_len
        if num_choruses <= 1:
            env.append(1.0)
            continue
        if ch == num_choruses - 1:
            env.append(0.72)  # out-chorus settles back down
        else:
            frac = ch / max(1, num_choruses - 1)
            env.append(0.45 + 0.55 * frac)
    return env


def _is_last_bar_of_chorus(bar, chord_len):
    return (bar % chord_len) == (chord_len - 1)


# =============================================================================
# JAZZ (swing changes)
# =============================================================================

def gen_jazz(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    notes = []
    scale = "dorian" if minor else "major"
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)
    scale_len = len(SCALES[scale])
    chord_len = 4

    def map_jazz_quality(deg):
        return extend_dominant(diatonic_seventh(scale, deg))

    degree_seq = _build_degree_sequence(scale, num_bars, bars_per_phrase=8, chord_len=chord_len)
    envelope = _chorus_envelope(num_bars, chord_len=chord_len)

    prev_comp = None
    prev_mel_val = None

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_jazz_quality(deg)
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % scale_len]
        intensity = envelope[bar]

        # Comping voicing density (color-tone probability) rises with the
        # chorus arc instead of a flat 0.2 chance start to finish.
        color_prob = 0.10 + 0.30 * intensity
        comp_intervals = maybe_add_color(shell_intervals(qual), prob=color_prob)
        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=3)
        comp_names = realize(comp_pitches)
        prev_comp = comp_pitches

        next_bar = (bar + 1) % num_bars
        next_deg = degree_seq[next_bar]
        next_root_pc = key_pc + SCALES[scale][next_deg % scale_len]

        # Stepwise walking bass for any beats_per_bar; at higher chorus
        # intensity, occasionally insert a chromatic passing tone on an
        # interior beat instead of the plain scale step (double-time feel).
        walk = []
        for b in range(beats_per_bar):
            if b == 0:
                walk.append(root_pc)
            elif b == beats_per_bar - 1 and beats_per_bar > 1:
                walk.append(next_root_pc - 1)
            else:
                diatonic = key_pc + SCALES[scale][(deg + b) % scale_len]
                if random.random() < 0.15 * intensity:
                    walk.append(diatonic - 1)  # chromatic approach, energetic bars only
                else:
                    walk.append(diatonic)
        for b, pc_ in enumerate(walk):
            notes.append(mk(s0 + b * 4, note_name(pc_, 2), "4n", (0.6 + 0.05 * (b == 0)) * (0.75 + 0.25 * intensity), steps))

        # Comping on the "and" of every beat except the first, scaled to
        # any beats_per_bar; density of actually-struck hits rises with
        # chorus intensity rather than firing every single time.
        comp_beats = [b + 0.5 for b in range(1, beats_per_bar)]
        for b_idx in comp_beats:
            off = int(b_idx * 4)
            if s0 + off < s0 + bar_steps and random.random() < (0.55 + 0.35 * intensity):
                for note in comp_names:
                    notes.append(mk(s0 + off, note, "8n", 0.35 * (0.7 + 0.3 * intensity), steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = (0, 1, 2, 3) if len(mel_chord) > 3 else (0, 1, 2)
        mel_notes_cnt = max(2, int(beats_per_bar * (1.1 + 0.6 * intensity)))
        mel_idx = contour_sequence(mel_notes_cnt, choices=mel_choices, start=carry_start(mel_choices, prev_mel_val))
        for i, ci in enumerate(mel_idx):
            step = s0 + 2 + i * 2
            if step >= s0 + bar_steps:
                continue
            note = mel_chord[ci % len(mel_chord)]
            notes.append(mk(step, note, "8n", (0.5 + random.uniform(0, 0.15)) * (0.75 + 0.25 * intensity), steps))
        prev_mel_val = mel_idx[-1]

        # Blue-note ornament: was hardwired to one specific bar of every
        # cycle, one fixed interval, one fixed position. Now probabilistic
        # (rising with chorus intensity), interval chosen from the classic
        # b3/b5/b7 blue-note set, and position varies within the bar.
        blue_prob = 0.15 + 0.35 * intensity
        if random.random() < blue_prob:
            blue_interval = random.choice([3, 6, 10])  # b3, b5, b7
            blue = note_name(root_pc + blue_interval, 5)
            blue_step = s0 + random.choice([max(2, bar_steps // 3), min(bar_steps - 2, 10), bar_steps - 3])
            blue_step = max(0, min(blue_step, steps - 1))
            notes.append(mk(blue_step, blue, "16n", 0.45 + 0.2 * intensity, steps))

    return notes


# =============================================================================
# BLUES
# =============================================================================

def gen_blues(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "blues"
    chord_len = 4
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    degree_seq = _build_degree_sequence("major", num_bars, bars_per_phrase=8, chord_len=chord_len)
    envelope = _chorus_envelope(num_bars, chord_len=chord_len)

    # Several stock left-hand patterns instead of one boogie riff forever;
    # picked once per chorus so the groove stays recognizable within a
    # chorus but the tune isn't locked to a single pattern start to finish.
    bass_pattern_bank = [
        [0, 7, 9, 7],        # classic boogie root-5th-6th-5th
        [0, 4, 7, 9],        # ascending triad + 6th
        [0, 7, 10, 7],       # root-5th-b7th-5th (dominant flavor)
        [0, 3, 7, 3],        # root-b3-5th-b3 (minor-blues tilt)
    ]
    current_pattern = random.choice(bass_pattern_bank)

    prev_comp = None
    prev_mel = None

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = "dom7"
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES["major"][deg]
        intensity = envelope[bar]

        if bar % chord_len == 0 and bar > 0:
            current_pattern = random.choice(bass_pattern_bank)

        last_bar = _is_last_bar_of_chorus(bar, chord_len)

        if last_bar and bar_steps >= 8:
            # Turnaround: chromatic descent from the tonic down toward the
            # V, landing there for the next chorus — replaces the plain
            # boogie riff only on the cycle's final bar.
            v_pc = key_pc + SCALES["major"][4]
            desc_len = beats_per_bar * 2
            for e in range(desc_len):
                step = s0 + e * 2
                frac = e / max(1, desc_len - 1)
                pc_ = round(root_pc + (v_pc - root_pc) * frac)
                vel = 0.7 if e == 0 else (0.65 if e % 2 == 0 else 0.5)
                notes.append(mk(step, note_name(pc_, 2), "8n", vel, steps))
        else:
            for e in range(beats_per_bar * 2):
                p_idx = e % len(current_pattern)
                step = s0 + e * 2
                vel = (0.75 if e == 0 else (0.7 if e % 2 == 0 else 0.5)) * (0.8 + 0.2 * intensity)
                notes.append(mk(step, note_name(root_pc + current_pattern[p_idx], 2), "8n", vel, steps))

        comp_intervals = shell_intervals(qual)
        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=3)
        for b in range(beats_per_bar):
            if b % 2 == 1 and random.random() < (0.6 + 0.3 * intensity):
                off = b * 4 + 2
                for note in realize(comp_pitches):
                    notes.append(mk(s0 + off, note, "8n", 0.4 * (0.7 + 0.3 * intensity), steps))
        prev_comp = comp_pitches

        mel_choices = (0, 1, 2, 3, 4, 5)
        start = carry_start(mel_choices, prev_mel)
        mel_cnt = beats_per_bar * 2
        mel_contour = contour_sequence(mel_cnt, choices=mel_choices, start=start, reversal_bias=0.45)
        note_prob = 0.55 + 0.3 * intensity
        for i, ci in enumerate(mel_contour):
            step = s0 + i * 2
            if random.random() < note_prob:
                notes.append(mk(step, note_name(key_pc + SCALES["blues"][ci], 5), "8n",
                                (0.6 + random.uniform(0, 0.1)) * (0.8 + 0.2 * intensity), steps))
        prev_mel = mel_contour[-1]

    return notes


# =============================================================================
# RAGTIME
# =============================================================================

def gen_ragtime(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    chord_len = 4
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    def map_ragtime(d):
        return "dom7" if d in (1, 4, 5, 6) else ("min" if d in (2,) else "maj")

    degree_seq = _build_degree_sequence(scale, num_bars, bars_per_phrase=8, chord_len=chord_len)
    envelope = _chorus_envelope(num_bars, chord_len=chord_len)

    # Multiple syncopation cells (as fractions of the bar, rescaled to
    # bar_steps so any beats_per_bar still lands correctly), swapped every
    # 8 bars — a rag's A-strain / trio sections traditionally do shift
    # their syncopation character, so a single fixed cell for the whole
    # piece undersells the form.
    rhythm_bank = [
        [0/16, 3/16, 6/16, 8/16, 11/16, 14/16],   # original cakewalk cell
        [0/16, 2/16, 5/16, 8/16, 10/16, 13/16],   # tighter syncopation
        [0/16, 3/16, 6/16, 9/16, 12/16, 14/16],   # even triplet-leaning feel
    ]
    section_len = 8
    current_rhythm = random.choice(rhythm_bank)

    prev_mel = None

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_ragtime(deg)
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        intensity = envelope[bar]

        if bar % section_len == 0:
            current_rhythm = random.choice([r for r in rhythm_bank if r != current_rhythm] or rhythm_bank)

        chord_ivs = CHORD_QUALITIES[qual]
        chord_notes = [note_name(root_pc + iv, 3) for iv in chord_ivs]

        for b in range(beats_per_bar):
            if b % 2 == 0:
                # Occasionally a passing tone instead of the plain 5th,
                # for stride-piano forward motion in busier bars.
                if b % 4 != 0 and random.random() < 0.2 * intensity:
                    bass_pc = root_pc + chord_ivs[2 % len(chord_ivs)] + random.choice([-1, 1])
                else:
                    bass_pc = root_pc + (chord_ivs[0] if b % 4 == 0 else chord_ivs[2 % len(chord_ivs)])
                notes.append(mk(s0 + b * 4, note_name(bass_pc, 2), "8n", 0.7 * (0.8 + 0.2 * intensity), steps))
            else:
                for cn in chord_notes:
                    notes.append(mk(s0 + b * 4, cn, "8n", 0.5 * (0.75 + 0.25 * intensity), steps))

        mel_choices = (0, 1, 2, 4, 5)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start)

        rhythm_pattern = sorted(set(int(round(f * bar_steps)) for f in current_rhythm))
        rhythm_pattern = [r for r in rhythm_pattern if r < bar_steps]
        for r_step in rhythm_pattern:
            ci = mel_contour[r_step % len(mel_contour)]
            notes.append(mk(s0 + r_step, scale_tone(key_pc, scale, deg + ci, 5), "8n",
                            0.65 * (0.8 + 0.2 * intensity), steps))
        prev_mel = mel_contour[-1]

    return notes


# =============================================================================
# BOSSA NOVA
# =============================================================================

def gen_bossa_nova(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    chord_len = 4
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    def map_bossa(d):
        return {0:"maj9", 1:"min9", 2:"min7", 3:"maj9", 4:"dom9", 5:"min7", 6:"m7b5"}.get(d, "maj9")

    degree_seq = _build_degree_sequence(scale, num_bars, bars_per_phrase=8, chord_len=chord_len)
    envelope = _chorus_envelope(num_bars, chord_len=chord_len)

    # Partido-alto style comping cells: sequences of step increments used to
    # advance through the bar. Previously fixed to a single [3,4,3,4...]
    # cadence for the entire tune; now several stock cells, swapped by
    # section so the groove still breathes across a longer arrangement.
    cell_bank = [
        [3, 4],
        [4, 3],
        [3, 3, 2],
        [4, 4, 2, 2] if False else [3, 4, 3],  # keep list lengths simple/safe
    ]
    section_len = 8
    current_cell = random.choice(cell_bank)

    prev_mel = None

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_bossa(deg)
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        intensity = envelope[bar]

        if bar % section_len == 0:
            current_cell = random.choice([c for c in cell_bank if c != current_cell] or cell_bank)

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
        idx = 0
        while c < bar_steps:
            comp_steps.append(c)
            c += current_cell[idx % len(current_cell)]
            idx += 1

        for c_step in comp_steps:
            for note in comp_names:
                notes.append(mk(s0 + c_step, note, "8n", (0.45 + random.uniform(0, 0.1)) * (0.75 + 0.25 * intensity), steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps // 2, choices=mel_choices, start=start, reversal_bias=0.3)

        mel_steps = [s for s in range(2, bar_steps, 3)]
        mel_prob = 0.55 + 0.3 * intensity
        for m_idx, m_step in enumerate(mel_steps):
            if random.random() < mel_prob:
                ci = mel_contour[m_idx % len(mel_contour)]
                notes.append(mk(s0 + m_step, mel_chord[ci], "8n", (0.6 + random.uniform(0, 0.1)) * (0.8 + 0.2 * intensity), steps))

        prev_mel = mel_contour[-1]

    return notes


# =============================================================================
# NEO SOUL
# =============================================================================

def gen_neo_soul(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "major"
    chord_len = 4
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    def map_neo_soul(d):
        return {0:"maj9", 1:"min9", 2:"min9", 3:"maj9", 4:"dom13", 5:"min9", 6:"m7b5"}.get(d, "maj9")

    degree_seq = _build_degree_sequence(scale, num_bars, bars_per_phrase=8, chord_len=chord_len)
    envelope = _chorus_envelope(num_bars, chord_len=chord_len)

    # Voicing-index variants for comping (rootless-style selections from the
    # extended chord tones), swapped every section instead of one fixed
    # [ivs[1], ivs[3], ...] shape used identically for the whole tune.
    voicing_variants = [
        lambda ivs: [ivs[1], ivs[3]] if len(ivs) >= 4 else [ivs[1], ivs[2]],
        lambda ivs: [ivs[2], ivs[3]] if len(ivs) >= 4 else [ivs[0], ivs[2]],
        lambda ivs: [ivs[1], ivs[2], ivs[3]] if len(ivs) >= 4 else [ivs[1], ivs[2]],
    ]
    section_len = 8
    current_voicing_fn = random.choice(voicing_variants)

    prev_comp = None
    prev_mel = None

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_neo_soul(deg)
        s0 = bar * bar_steps
        intensity = envelope[bar]

        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        if deg == 0 and qual == "dim7":
            root_pc += 1

        if bar % section_len == 0:
            current_voicing_fn = random.choice([f for f in voicing_variants if f != current_voicing_fn] or voicing_variants)

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.65, steps))
        if beats_per_bar >= 4:
            notes.append(mk(s0 + 8, note_name(root_pc, 2), "4n", 0.5, steps))

        ivs = CHORD_QUALITIES[qual]
        comp_intervals = current_voicing_fn(ivs)
        if len(ivs) > 4:
            comp_intervals.append(ivs[4])
        if len(ivs) > 5:
            comp_intervals.append(ivs[5])

        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=4)
        comp_names = realize(comp_pitches)
        prev_comp = comp_pitches

        hits = [0]
        for b in range(1, beats_per_bar):
            if random.random() < (0.55 + 0.3 * intensity):
                hits.append(b * 4 + random.choice([0, 1]))

        for h in hits:
            if h < bar_steps and random.random() < (0.65 + 0.25 * intensity):
                vel = 0.5 if h in (0, 8) else 0.4
                for note in comp_names:
                    notes.append(mk(s0 + h, note, "8n", vel + random.uniform(0, 0.05), steps))

        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = tuple(range(len(mel_chord)))
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start, reversal_bias=0.4)

        mel_prob = 0.20 + 0.25 * intensity
        for m_step in range(bar_steps):
            if random.random() < mel_prob:
                ci = mel_contour[m_step % len(mel_contour)]
                target_note = mel_chord[ci]

                if random.random() < 0.4:
                    target_pc = root_pc + ivs[ci % len(ivs)]
                    grace = note_name(target_pc - 1, 5)
                    grace_step = max(0, s0 + m_step - 1)
                    notes.append(mk(grace_step, grace, "32n", 0.4, steps))

                notes.append(mk(s0 + m_step, target_note, "16n", (0.65 + random.uniform(0, 0.1)) * (0.8 + 0.2 * intensity), steps))

        prev_mel = mel_contour[-1]

    return notes
