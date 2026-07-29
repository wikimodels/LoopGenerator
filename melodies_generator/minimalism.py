import random
import math
from .core import *
def gen_einaudi(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    notes = []
    scale = "natural_minor" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def map_einaudi(d):
        if minor:
            return {0:"min", 1:"dim", 2:"maj", 3:"min", 4:"min", 5:"maj", 6:"maj"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")
    prog = [(d, map_einaudi(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None

    # FIX #14: pattern_type used to be `bar % 4`, a fixed cycle keyed purely
    # to bar index. Every call of gen_einaudi (any seed, any key) therefore
    # produced the exact same 0-1-2-3-0-1-2-3... arpeggio-shape sequence,
    # so the only thing that varied between seeds was the harmony/melody,
    # not the arpeggio's structural shape. pattern_cycle now shuffles the
    # same 4 pattern types into a random order once per call (seed-dependent),
    # so different generate_loop() calls get a genuinely different
    # arpeggio-shape sequence, while each individual loop still cycles
    # through its 4 shapes predictably bar-to-bar (no added within-loop
    # randomness — cyclicity inside one loop is intentional for a Suno seed).
    pattern_cycle = [0, 1, 2, 3]
    random.shuffle(pattern_cycle)

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        chord_ivs = CHORD_QUALITIES[qual]
        # Richer arpeggio pool spanning multiple octaves
        arp_pitches = [
            root_pc - 12,                  # Root low
            root_pc - 12 + chord_ivs[1],   # Third low
            root_pc - 12 + chord_ivs[2],   # Fifth low
            root_pc,                       # Root mid
            root_pc + chord_ivs[1],        # Third mid
            root_pc + chord_ivs[2],        # Fifth mid
            root_pc + 12                   # Root high
        ]

        # Dynamic arpeggio pattern, now drawn from the seed-shuffled cycle
        # instead of a hardcoded bar % 4.
        pattern_type = pattern_cycle[bar % len(pattern_cycle)]
        arp_len = beats_per_bar * 2
        
        for b in range(arp_len):
            step = s0 + b * 2
            
            if pattern_type == 0 or pattern_type == 2:
                # Up and down sweeping
                idx = b if b < 4 else 7 - b
                if idx < 0 or idx >= len(arp_pitches): idx = 0
            elif pattern_type == 1:
                # Alternating high/low
                idx = (b // 2) if b % 2 == 0 else (b // 2) + 3
                if idx >= len(arp_pitches): idx = len(arp_pitches) - 1
            else:
                # Gentle cascade down
                idx = 5 - (b % 4)
                
            # Random occasional skip for human feel
            if random.random() < 0.05:
                continue
                
            velocity = 0.4 + 0.15 * (b % 2 == 0) + random.uniform(-0.05, 0.05)
            notes.append(mk(step, note_name(arp_pitches[idx], 3), "8n", velocity, steps))

        # Bass anchor
        notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.55, steps))

        # Dynamic Melody: Not just one note every 2 bars!
        # Einaudi melodies are simple, melancholic, often 2-4 notes per phrase.
        if bar % 4 != 3: # Rest on the 4th bar of a phrase
            num_mel_notes = random.choice([1, 2, 3])
            mel_choices = (0, 1, 2, 4)
            start = carry_start(mel_choices, prev_mel)
            mel_contour = contour_sequence(num_mel_notes, choices=mel_choices, start=start)
            
            mel_step = s0
            for i, m_deg in enumerate(mel_contour):
                # Distribute melody notes nicely (e.g., beat 1, beat 3, or syncopated)
                offset = [0, 4, 8, 12][i % 4]
                if random.random() < 0.2: 
                    offset += 2 # slight syncopation
                
                # Higher octave for melody
                notes.append(mk(s0 + offset, scale_tone(key_pc, scale, deg + m_deg, 5), "2n", 0.7 + random.uniform(0, 0.1), steps))
                prev_mel = m_deg

    return notes

def gen_glass(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    notes = []
    scale = "dorian" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def map_glass(d):
        if minor:
            return {0:"min", 1:"min", 2:"maj", 3:"maj", 4:"min", 5:"dim", 6:"maj"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")
    prog = [(d, map_glass(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    # FIX #15: pattern_len was a hardcoded constant (3), so the additive-
    # process "grouping" of the eighth-note pattern was identical across
    # every call regardless of seed. It's now drawn once per call from a
    # small set of musically sensible group lengths (2, 3, or 4 eighths),
    # which is exactly the kind of "shifting metric grouping" Glass's own
    # music uses, and gives different seeds a genuinely different pulse feel.
    pattern_len = random.choice([2, 3, 4])

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        chord_ivs = CHORD_QUALITIES[qual]
        # FIX #15: added a third candidate shape alongside the original two,
        # so the per-bar random.random() draw below has more than a binary
        # choice to pick from — more shape variety per call.
        pattern_candidates = [
            [root_pc, root_pc + chord_ivs[1], root_pc + chord_ivs[2]],
            [root_pc, root_pc + chord_ivs[2], root_pc + 12],
            [root_pc + chord_ivs[1], root_pc + chord_ivs[2], root_pc + 12],
        ]
        pattern = random.choice(pattern_candidates)

        for i in range(beats_per_bar * 2):
            global_eighth = bar * (beats_per_bar * 2) + i
            p_idx = global_eighth % pattern_len % len(pattern)
            step = s0 + i * 2
            vel = 0.6 if p_idx == 0 else 0.4
            notes.append(mk(step, note_name(pattern[p_idx], 4), "8n", vel, steps))

            if bar % 2 == 0 and i == 0:
                notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.5, steps))

    return notes

def gen_tiersen(key_pc, scale_name, bpm, steps, beats_per_bar=3, minor=True):
    notes = []
    scale = "harmonic_minor" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def map_tiersen(d):
        if minor:
            return {0:"min", 1:"dim", 2:"aug", 3:"min", 4:"dom7", 5:"maj", 6:"dim"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"dom7", 5:"min", 6:"dim"}.get(d, "maj")
    prog = [(d, map_tiersen(d)) for d in degrees]
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_mel = None

    # FIX #16: the left-hand ostinato used to always voice the chord's
    # intervals in the same fixed ascending order (root, 3rd, 5th, ...)
    # on every single off-beat, for every seed. ostinato_order now
    # shuffles that once per call so the arpeggiated ostinato figure
    # itself differs between calls, not just the harmony/melody riding
    # on top of it.
    ostinato_order = None  # resolved per-chord below since chord sizes vary

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.65, steps))

        chord_ivs = CHORD_QUALITIES[qual]
        chord_notes = [note_name(root_pc + iv, 3) for iv in chord_ivs]
        # FIX #16: shuffle the ostinato's internal note order once per bar
        # (seed-dependent), instead of always playing chord_notes in the
        # same fixed ascending order every time.
        ostinato_notes = list(chord_notes)
        random.shuffle(ostinato_notes)
        for b in range(1, beats_per_bar):
            for cn in ostinato_notes:
                notes.append(mk(s0 + b * 4, cn, "4n", 0.45, steps))

        mel_choices = (0, 1, 2, 3, 4, 5)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start, reversal_bias=0.2, max_run=4)

        for i, ci in enumerate(mel_contour):
            step = s0 + i
            notes.append(mk(step, scale_tone(key_pc, scale, deg + ci, 5), "16n", 0.5 + random.uniform(0, 0.15), steps))

        prev_mel = mel_contour[-1]

    return notes

def gen_frahm(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """FIX #3: takes an explicit `minor` flag instead of internally rolling
    a coin (70% minor) that ignored the scale actually requested by the
    caller/style metadata."""
    notes = []
    scale = "natural_minor" if minor else "major"
    degrees = generate_harmony(scale, length=4)
    def map_frahm(d):
        if minor:
            return {0:"min", 1:"dim", 2:"maj", 3:"min", 4:"min", 5:"maj", 6:"maj"}.get(d, "min")
        return {0:"maj", 1:"min", 2:"min", 3:"maj", 4:"maj", 5:"min", 6:"dim"}.get(d, "maj")
    prog = [(d, map_frahm(d)) for d in degrees]

    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    prev_pad = None
    prev_mel = None

    # FIX #17: the ambient ostinato shape (root, 5th, octave, oct+3rd) was a
    # single hardcoded contour used identically on every call. shape_offsets
    # now picks from a couple of comparably "flowing" 4-note contours once
    # per call, so different seeds get a different ostinato shape instead of
    # only different harmony/melody riding on the exact same shape.
    shape_offsets_candidates = [
        (0, 2, 3, 1),  # root, 5th, octave, oct+3rd (original shape)
        (0, 1, 2, 3),  # root, 3rd, 5th, octave (simple ascending)
        (2, 0, 3, 1),  # 5th, root, oct+3rd, octave
    ]
    shape_offsets = random.choice(shape_offsets_candidates)

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        if bar % 2 == 0:
            pad_pitches = voice_lead(CHORD_QUALITIES[qual], root_pc, prev_pad, anchor_octave=3)
            for note in realize(pad_pitches):
                notes.append(mk(s0, note, "1n", 0.25, steps))
            notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.3, steps))
            prev_pad = pad_pitches

        # Flowing 4-note ambient ostinato, shape now drawn from
        # shape_offsets (root/5th/octave/oct+3rd building blocks) instead
        # of a single hardcoded contour.
        ivs = CHORD_QUALITIES[qual]
        shape_pool = [
            note_name(root_pc, 4),               # 0: root
            note_name(root_pc + ivs[1], 4),       # 1: 3rd
            note_name(root_pc + ivs[2], 4),       # 2: 5th
            note_name(root_pc + 12 + ivs[1], 4),  # 3: octave + 3rd
        ]
        pattern = [shape_pool[i] for i in shape_offsets]
        for i in range(beats_per_bar * 2):
            step = s0 + i * 2
            p_idx = i % len(pattern)
            notes.append(mk(step, pattern[p_idx], "8n", 0.35 + 0.05 * (i % 2 == 0), steps))

        # Sparse, floating melody in the right hand
        if bar % 2 == 1:
            mel_choices = (0, 1, 2, 4)
            start = carry_start(mel_choices, prev_mel)
            mel_contour = contour_sequence(1, choices=mel_choices, start=start)
            notes.append(mk(s0, scale_tone(key_pc, scale, deg + mel_contour[0], 5), "2n", 0.55, steps))
            prev_mel = mel_contour[0]

    return notes

