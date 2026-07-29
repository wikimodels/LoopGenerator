import random
import math
from .core import *

# =============================================================================
# SHARED HELPERS
# =============================================================================

def _build_progression(scale, num_bars, bars_per_phrase=8, chord_len=4):
    """
    Harmony that actually develops over long tracks instead of looping the
    same 4-chord cell forever. A fresh `generate_harmony` call fires every
    `bars_per_phrase` bars, so short loops (num_bars <= bars_per_phrase)
    behave exactly as before (one static progression), while longer tracks
    get slow harmonic evolution — new phrase material every ~2 loops,
    matching how minimalist pieces gradually shift their harmonic cell.
    """
    prog = []
    degrees = None
    for bar in range(num_bars):
        if bar % bars_per_phrase == 0:
            degrees = generate_harmony(scale, length=chord_len)
        prog.append(degrees[bar % chord_len])
    return prog


def _density_envelope(num_bars):
    """
    Additive-process arc: 0..1 intensity per bar. Builds from sparse to full
    texture over the first third, sustains, then thins out over the final
    third — the classic minimalist accumulation/recession shape (Glass,
    Reich, and by extension the piano-minimalist Einaudi/Frahm/Tiersen
    lineage all lean on this). Short pieces (<=4 bars) stay at full
    intensity throughout since there's no room for a real arc.
    """
    if num_bars <= 4:
        return [1.0] * num_bars
    build_end = max(1, num_bars // 3)
    fade_start = num_bars - max(1, num_bars // 3)
    env = []
    for b in range(num_bars):
        if b < build_end:
            env.append(0.30 + 0.70 * (b / build_end))
        elif b >= fade_start:
            remaining = num_bars - b
            span = max(1, num_bars - fade_start)
            env.append(0.30 + 0.70 * (remaining / span))
        else:
            env.append(1.0)
    return env


def _bar_offsets(bar_steps, count):
    """Evenly spaced step offsets within a bar for `count` events, replacing
    hardcoded [0,4,8,12]-style lists that silently assumed 4/4 at 16 steps."""
    if count <= 0:
        return []
    return [int(round(k * bar_steps / count)) for k in range(count)]


# =============================================================================
# EINAUDI
# =============================================================================

def gen_einaudi(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    notes = []
    scale = "natural_minor" if minor else "major"
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    def map_einaudi(d):
        if minor:
            return {0:"min", 1:"dim", 2:"maj", 3:"min", 4:"min", 5:"maj", 6:"maj"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")

    degree_seq = _build_progression(scale, num_bars, bars_per_phrase=8, chord_len=4)
    envelope = _density_envelope(num_bars)

    prev_mel = None

    # Shuffle once per call so the arpeggio-shape *sequence* differs between
    # seeds, same intent as before — but pattern_type 2 now has its own
    # genuinely distinct shape (it used to compute the identical index
    # formula as pattern_type 0, making the "4-way" shuffle only a 3-way
    # choice in practice).
    pattern_cycle = [0, 1, 2, 3]
    random.shuffle(pattern_cycle)

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_einaudi(deg)
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        intensity = envelope[bar]

        chord_ivs = CHORD_QUALITIES[qual]
        arp_pitches = [
            root_pc - 12,
            root_pc - 12 + chord_ivs[1],
            root_pc - 12 + chord_ivs[2],
            root_pc,
            root_pc + chord_ivs[1],
            root_pc + chord_ivs[2],
            root_pc + 12
        ]

        pattern_type = pattern_cycle[bar % len(pattern_cycle)]
        arp_len = beats_per_bar * 2

        # Additive process: how many of the arp_len slots actually sound
        # scales with the density envelope, so quiet opening/closing bars
        # genuinely thin out rather than just being quieter at fixed density.
        active_slots = max(2, round(arp_len * (0.4 + 0.6 * intensity)))

        for b in range(arp_len):
            step = s0 + b * 2

            if pattern_type == 0:
                # Up and down sweeping
                idx = b if b < 4 else 7 - b
            elif pattern_type == 1:
                # Alternating high/low
                idx = (b // 2) if b % 2 == 0 else (b // 2) + 3
            elif pattern_type == 2:
                # Broken-thirds zigzag through the low/mid register —
                # distinct contour from pattern 0 (previously identical)
                zig = [0, 2, 1, 3, 0, 2, 1, 3]
                idx = zig[b % len(zig)]
            else:
                # Gentle cascade down
                idx = 5 - (b % 4)

            if idx < 0 or idx >= len(arp_pitches):
                idx = 0

            if b >= active_slots:
                continue
            if random.random() < 0.05:
                continue

            velocity = (0.4 + 0.15 * (b % 2 == 0) + random.uniform(-0.05, 0.05)) * (0.6 + 0.4 * intensity)
            notes.append(mk(step, note_name(arp_pitches[idx], 3), "8n", velocity, steps))

        # Bass anchor — present whenever the envelope is above a low floor,
        # so the very first/last bars of the arc can drop it entirely.
        if intensity > 0.35 or bar == 0:
            notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.55 * (0.7 + 0.3 * intensity), steps))

        # Melody: rest probability now tied to the envelope (quiet bars are
        # more likely to rest) instead of a rigid bar % 4 != 3 rule, and
        # offsets are derived from bar_steps so non-4/4 meters lay out right.
        rest_chance = 0.12 + 0.35 * (1 - intensity)
        if random.random() > rest_chance:
            num_mel_notes = random.choice([1, 2, 3])
            mel_choices = (0, 1, 2, 4)
            start = carry_start(mel_choices, prev_mel)
            mel_contour = contour_sequence(num_mel_notes, choices=mel_choices, start=start)

            offsets = _bar_offsets(bar_steps, max(num_mel_notes, 1))
            for i, m_deg in enumerate(mel_contour):
                offset = offsets[i % len(offsets)]
                if random.random() < 0.2:
                    offset = min(bar_steps - 1, offset + 2)
                vel = (0.7 + random.uniform(0, 0.1)) * (0.65 + 0.35 * intensity)
                notes.append(mk(s0 + offset, scale_tone(key_pc, scale, deg + m_deg, 5), "2n", vel, steps))
                prev_mel = m_deg

    return notes


# =============================================================================
# GLASS
# =============================================================================

def gen_glass(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    notes = []
    scale = "dorian" if minor else "major"
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    def map_glass(d):
        if minor:
            return {0:"min", 1:"min", 2:"maj", 3:"maj", 4:"min", 5:"dim", 6:"maj"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")

    degree_seq = _build_progression(scale, num_bars, bars_per_phrase=8, chord_len=4)
    envelope = _density_envelope(num_bars)

    # Base metric grouping still randomized once per call (shifting group
    # length is itself a signature Glass device), but the number of *active*
    # notes within the pattern now genuinely accumulates/recedes across the
    # piece — a real additive process rather than a single fixed 2-or-3-note
    # shape used uniformly start to finish.
    pattern_len = random.choice([2, 3, 4])

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_glass(deg)
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        intensity = envelope[bar]

        chord_ivs = CHORD_QUALITIES[qual]
        pattern_candidates = [
            [root_pc, root_pc + chord_ivs[1], root_pc + chord_ivs[2]],
            [root_pc, root_pc + chord_ivs[2], root_pc + 12],
            [root_pc + chord_ivs[1], root_pc + chord_ivs[2], root_pc + 12],
        ]
        full_pattern = random.choice(pattern_candidates)

        # Additive process: at low intensity only the first note of the
        # pattern sounds (a drone-like pulse); it accumulates notes as the
        # envelope rises, reaching the full pattern at peak intensity.
        active_notes = max(1, round(len(full_pattern) * (0.34 + 0.66 * intensity)))
        pattern = full_pattern[:active_notes]

        for i in range(beats_per_bar * 2):
            global_eighth = bar * (beats_per_bar * 2) + i
            p_idx = global_eighth % pattern_len % len(pattern)
            step = s0 + i * 2
            vel = (0.6 if p_idx == 0 else 0.4) * (0.6 + 0.4 * intensity)
            notes.append(mk(step, note_name(pattern[p_idx], 4), "8n", vel, steps))

            if bar % 2 == 0 and i == 0 and intensity > 0.4:
                notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.5 * (0.6 + 0.4 * intensity), steps))

    return notes


# =============================================================================
# TIERSEN
# =============================================================================

def gen_tiersen(key_pc, scale_name, bpm, steps, beats_per_bar=3, minor=True):
    notes = []
    scale = "harmonic_minor" if minor else "major"
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    def map_tiersen(d):
        if minor:
            return {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"dom7", 5:"min", 6:"dim"}.get(d, "maj")

    degree_seq = _build_progression(scale, num_bars, bars_per_phrase=8, chord_len=4)
    envelope = _density_envelope(num_bars)

    prev_mel = None
    prev_chord_key = None
    ostinato_notes = None

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_tiersen(deg)
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        intensity = envelope[bar]

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.65 * (0.6 + 0.4 * intensity), steps))

        chord_ivs = CHORD_QUALITIES[qual]
        chord_notes = [note_name(root_pc + iv, 3) for iv in chord_ivs]

        # The ostinato figure now only reshuffles when the underlying chord
        # actually changes, so the same harmonic function keeps the same
        # recognizable left-hand shape across repeated bars (as in Tiersen's
        # actual writing) instead of re-randomizing every single bar.
        chord_key = (deg, qual)
        if chord_key != prev_chord_key or ostinato_notes is None:
            ostinato_notes = list(chord_notes)
            random.shuffle(ostinato_notes)
            prev_chord_key = chord_key

        # Additive process: quiet bars drop to a thinner subset of the
        # ostinato notes rather than always playing the full figure.
        active_count = max(1, round(len(ostinato_notes) * (0.5 + 0.5 * intensity)))
        active_ostinato = ostinato_notes[:active_count]

        for b in range(1, beats_per_bar):
            for cn in active_ostinato:
                notes.append(mk(s0 + b * 4, cn, "4n", 0.45 * (0.6 + 0.4 * intensity), steps))

        mel_choices = (0, 1, 2, 3, 4, 5)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start, reversal_bias=0.2, max_run=4)

        for i, ci in enumerate(mel_contour):
            step = s0 + i
            # Sparse melody bars during low-intensity sections: skip some
            # notes probabilistically instead of always playing every step.
            if random.random() < (0.12 * (1 - intensity)):
                continue
            vel = (0.5 + random.uniform(0, 0.15)) * (0.6 + 0.4 * intensity)
            notes.append(mk(step, scale_tone(key_pc, scale, deg + ci, 5), "16n", vel, steps))

        prev_mel = mel_contour[-1]

    return notes


# =============================================================================
# FRAHM
# =============================================================================

def gen_frahm(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """Takes an explicit `minor` flag instead of internally rolling a coin
    that ignored the scale actually requested by the caller/style metadata."""
    notes = []
    scale = "natural_minor" if minor else "major"
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    def map_frahm(d):
        if minor:
            return {0:"min", 1:"dim", 2:"maj", 3:"min", 4:"min", 5:"maj", 6:"maj"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")

    degree_seq = _build_progression(scale, num_bars, bars_per_phrase=8, chord_len=4)
    envelope = _density_envelope(num_bars)

    prev_pad = None
    prev_mel = None

    shape_offsets_candidates = [
        (0, 2, 3, 1),  # root, 5th, octave, oct+3rd (original shape)
        (0, 1, 2, 3),  # root, 3rd, 5th, octave (simple ascending)
        (2, 0, 3, 1),  # 5th, root, oct+3rd, octave
    ]
    shape_offsets = random.choice(shape_offsets_candidates)

    # Instead of a rigid bar % 2 == 0 / == 1 alternation for pad vs. melody
    # (identical every single time regardless of seed or position in the
    # piece), scheduling is now probabilistic and envelope-aware: pads are
    # more likely to sustain through low-intensity (quiet, spacious) bars,
    # melody is more likely to surface at higher intensity, and either layer
    # can rest entirely for true silence — an expressive device this style
    # leans on heavily that the fixed alternation never allowed.
    pad_active_bar = None  # bar index the current pad was struck on, for holding

    for bar in range(num_bars):
        deg = degree_seq[bar]
        qual = map_frahm(deg)
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        intensity = envelope[bar]

        pad_prob = 0.35 + 0.35 * (1 - intensity)  # more likely to (re)strike pad in sparse bars
        strike_pad = (pad_active_bar is None) or (bar - pad_active_bar >= 2) or (random.random() < pad_prob * 0.3)

        if strike_pad:
            pad_pitches = voice_lead(CHORD_QUALITIES[qual], root_pc, prev_pad, anchor_octave=3)
            for note in realize(pad_pitches):
                notes.append(mk(s0, note, "1n", 0.25 * (0.6 + 0.4 * intensity), steps))
            notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.3 * (0.6 + 0.4 * intensity), steps))
            prev_pad = pad_pitches
            pad_active_bar = bar

        # Ambient ostinato — density-gated: at low intensity only a sparse
        # subset of the 8th-note grid plays (real additive accumulation),
        # rising to the full pattern at peak intensity.
        ivs = CHORD_QUALITIES[qual]
        shape_pool = [
            note_name(root_pc, 4),
            note_name(root_pc + ivs[1], 4),
            note_name(root_pc + ivs[2], 4),
            note_name(root_pc + 12 + ivs[1], 4),
        ]
        pattern = [shape_pool[i] for i in shape_offsets]
        total_slots = beats_per_bar * 2
        active_slots = max(2, round(total_slots * (0.35 + 0.65 * intensity)))
        for i in range(total_slots):
            if i >= active_slots and random.random() < 0.7:
                continue
            step = s0 + i * 2
            p_idx = i % len(pattern)
            notes.append(mk(step, pattern[p_idx], "8n", (0.35 + 0.05 * (i % 2 == 0)) * (0.5 + 0.5 * intensity), steps))

        # Sparse, floating melody — probability now scales with intensity
        # (more likely to surface as the piece builds) instead of a rigid
        # every-other-bar rule, and can be entirely silent in quiet bars.
        mel_prob = 0.20 + 0.55 * intensity
        if random.random() < mel_prob:
            mel_choices = (0, 1, 2, 4)
            start = carry_start(mel_choices, prev_mel)
            mel_contour = contour_sequence(1, choices=mel_choices, start=start)
            mel_offset = _bar_offsets(bar_steps, 1)[0]
            if random.random() < 0.3:
                mel_offset = min(bar_steps - 1, mel_offset + bar_steps // 4)
            notes.append(mk(s0 + mel_offset, scale_tone(key_pc, scale, deg + mel_contour[0], 5),
                            "2n", 0.55 * (0.7 + 0.3 * intensity), steps))
            prev_mel = mel_contour[0]

    return notes
