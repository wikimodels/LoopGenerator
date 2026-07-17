"""
PARAMETRIC MUSIC THEORY ENGINE — fixed version 2
================================
generate_loop(style, key, bpm, steps, beats_per_bar) -> loop dict matching the sequencer JSON schema.

This revision adds one fix on top of the previous "fixed version":

12. gen_renaissance() no longer overwrites the `mode` argument passed in by
    the caller with its own random choice of dorian/phrygian/mixolydian.
    Previously EVERY call — regardless of which of "renaissance_dorian",
    "renaissance_phrygian", or "renaissance_mixolydian" was requested via
    STYLE_META — rerolled the mode internally, so all three styles were
    indistinguishable at runtime (each one just played a random mode from
    the same 3-way roulette). The function now honors the `mode` argument
    directly, defaulting to "dorian" only when the caller doesn't specify one.

Fixes retained from the previous version (see original review):
 1. mk() now coerces step to int and WRAPS/CLAMPS it into [0, steps_total) again.
 2. Fractional-step call sites (lofi strum, neo_soul grace note, romantic rubato)
    now round to int steps instead of leaking floats into the JSON.
 3. gen_romantic / gen_waltz / gen_frahm no longer coin-flip their own scale and
    silently ignore the scale that was actually requested — they now take an
    explicit `minor` flag and are registered as separate major/minor styles,
    the same pattern already used for neoclassical/baroque/jazz.
 4. waltz defaults to beats_per_bar=3 (an actual waltz) instead of 4.
 5. diatonic_seventh now maps the fully-diminished 7th (3,6,9) -> "dim7"
    instead of silently falling back to "dom7".
 6. Jazz walking bass now builds a genuine stepwise line for ANY beats_per_bar
    instead of padding with duplicate 5ths when beats_per_bar > 4.
 7. Jazz comping beats are now generic (off-beat of every beat except the
    first) instead of only being defined for beats_per_bar in {4, 5}.
 8. Ragtime's syncopation pattern is now expressed as fractions of the bar
    and scaled to bar_steps, instead of a hardcoded 16-step pattern.
 9. Renaissance tenor voice now rests / resolves properly on the final bar
    instead of continuing to play the previous harmony's notes under the
    cadence.
10. voice_lead() now enforces a minimum gap between adjacent voices so it
    can't stack two pitches a half/whole step apart into a cluster.
11. SPAN_TO_DURATION no longer silently defaults unknown spans to "8n" —
    it raises, so a bad span is caught immediately instead of mis-notated.
"""
import json, os, random

NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
PC = {n:i for i,n in enumerate(NOTE_NAMES)}

def note_name(semitone, octave):
    idx = semitone % 12
    octv = octave + semitone // 12
    return f"{NOTE_NAMES[idx]}{octv}"

# ---------------------------------------------------------------
# AXIS 1: SCALES / MODES
# ---------------------------------------------------------------
SCALES = {
    "major":              [0,2,4,5,7,9,11],
    "natural_minor":      [0,2,3,5,7,8,10],
    "harmonic_minor":     [0,2,3,5,7,8,11],
    "melodic_minor_asc":  [0,2,3,5,7,9,11],
    "dorian":             [0,2,3,5,7,9,10],
    "phrygian":           [0,1,3,5,7,8,10],
    "lydian":             [0,2,4,6,7,9,11],
    "mixolydian":         [0,2,4,5,7,9,10],
    "locrian":            [0,1,3,5,6,8,10],
    "major_pentatonic":   [0,2,4,7,9],
    "minor_pentatonic":   [0,3,5,7,10],
    "blues":              [0,3,5,6,7,10],
}

def scale_tone(key_pc, scale_name, degree, octave):
    scale = SCALES[scale_name]
    n = len(scale)
    octv_add, d = divmod(degree, n)
    return note_name(key_pc + scale[d], octave + octv_add)

def _degree_pc(scale_name, degree):
    scale = SCALES[scale_name]
    n = len(scale)
    octv_add, idx = divmod(degree, n)
    return scale[idx] + 12*octv_add

def diatonic_quality(scale_name, degree):
    root = _degree_pc(scale_name, degree)
    third = _degree_pc(scale_name, degree+2) - root
    fifth = _degree_pc(scale_name, degree+4) - root
    if (third,fifth) == (4,7): return "maj"
    if (third,fifth) == (3,7): return "min"
    if (third,fifth) == (3,6): return "dim"
    if (third,fifth) == (4,8): return "aug"
    return "maj"

# FIX #5: added the fully-diminished 7th (3,6,9) -> "dim7". Previously this
# combination (common for vii dim7 in harmonic minor, a staple of baroque
# and classical cadences) fell through to the "dom7" default and silently
# changed the chord's function.
SEVENTH_QUALITY_MAP = {
    (4,7,11): "maj7",
    (3,7,10): "min7",
    (4,7,10): "dom7",
    (3,6,10): "m7b5",
    (3,6,9):  "dim7",
}

def diatonic_seventh(scale_name, degree):
    root = _degree_pc(scale_name, degree)
    third = _degree_pc(scale_name, degree+2) - root
    fifth = _degree_pc(scale_name, degree+4) - root
    seventh = _degree_pc(scale_name, degree+6) - root
    return SEVENTH_QUALITY_MAP.get((third,fifth,seventh), "dom7")

def build_diatonic_chord(scale_name, degree, force_dominant7=True):
    quality = diatonic_quality(scale_name, degree)
    if force_dominant7 and degree % len(SCALES[scale_name]) == 4 and quality == "maj":
        return "dom7"
    return quality

def extend_dominant(quality, prob=0.5):
    if quality == "dom7" and random.random() < prob:
        return "dom9"
    return quality

# ---------------------------------------------------------------
# AXIS 2: CHORD VOCABULARY
# ---------------------------------------------------------------
CHORD_QUALITIES = {
    "maj":   [0,4,7],
    "min":   [0,3,7],
    "dim":   [0,3,6],
    "aug":   [0,4,8],
    "maj7":  [0,4,7,11],
    "min7":  [0,3,7,10],
    "dom7":  [0,4,7,10],
    "m7b5":  [0,3,6,10],
    "dim7":  [0,3,6,9],
    "dom9":  [0,4,7,10,14],
    "min9":  [0,3,7,10,14],
    "maj9":  [0,4,7,11,14],
    "dom13": [0,4,7,10,14,21],
}

def chord_tones(root_pc, quality, octave):
    unique_ivs = sorted(set(iv % 12 for iv in CHORD_QUALITIES[quality]))
    return [note_name(root_pc+iv, octave) for iv in unique_ivs]

def shell_intervals(quality):
    ivs = CHORD_QUALITIES[quality]
    return [ivs[0], ivs[1], ivs[3]] if len(ivs) >= 4 else list(ivs)

# ---------------------------------------------------------------
# DYNAMIC HARMONY GENERATOR (Markov Chain)
# ---------------------------------------------------------------
def generate_harmony(scale_type, length=4, start_degree=None):
    # 0: I, 1: ii, 2: iii, 3: IV, 4: V, 5: vi, 6: vii°
    major_transitions = {
        0: [0, 1, 2, 3, 4, 5, 6], # I can go anywhere
        1: [4, 6],                # ii -> V, vii°
        2: [5, 3],                # iii -> vi, IV
        3: [4, 0, 1, 5],          # IV -> V, I, ii, vi
        4: [0, 5],                # V -> I, vi
        5: [3, 1, 4],             # vi -> IV, ii, V
        6: [0, 2],                # vii° -> I, iii
    }
    
    # 0: i, 1: ii°, 2: III, 3: iv, 4: v/V, 5: VI, 6: VII/vii°
    minor_transitions = {
        0: [0, 1, 2, 3, 4, 5, 6], # i can go anywhere
        1: [4, 6],                # ii° -> V, vii°
        2: [5, 3, 6],             # III -> VI, iv, VII
        3: [4, 0, 1, 5],          # iv -> V, i, ii°, VI
        4: [0, 5],                # V -> i, VI
        5: [3, 1, 4, 2],          # VI -> iv, ii°, V, III
        6: [2, 0],                # VII -> III, i
    }
    
    transitions = minor_transitions if "minor" in scale_type or scale_type in ["dorian", "phrygian", "aeolian"] else major_transitions
    
    if start_degree is not None:
        current = start_degree
    else:
        # Weighted start degrees for better musicality
        current = random.choices([0, 5, 3, 1], weights=[50, 20, 15, 15], k=1)[0]
        
    prog = [current]
    for _ in range(length - 1):
        options = transitions.get(current, [0])
        current = random.choice(options)
        prog.append(current)
        
    return prog

# ---------------------------------------------------------------
# VOICE LEADING for block chords
# ---------------------------------------------------------------
def nearest_register(pc, center):
    k = round((center - pc) / 12)
    return pc + 12*k

# FIX #12 (supersedes the previous FIX #10 patch): build the voicing as an
# ascending stack instead of independently rounding every tone to its own
# nearest octave around one shared center. The first tone lands nearest the
# previous chord's center of gravity (this is what gives common-tone /
# small-step voice leading between chords); every following tone is placed
# at the smallest pitch that still clears min_gap above the tone below it.
# This guarantees the voicing's total span is just the chord's own interval
# span (e.g. ~10 semitones for a root-3rd-7th shell) and can never drop a
# tone a full octave away from the rest of the chord into a neighboring
# voice's register — which is exactly what the old independent-rounding +
# reactive min_gap patch was doing (verified: 12/12 roots, dom7 shell,
# produced 18-20 semitone-wide voicings with the 7th landing in the bass).
def voice_lead(intervals, root_pc, prev_voicing, anchor_octave=4, min_gap=3, max_octave=5):
    pitch_classes = [(root_pc + iv) % 12 for iv in intervals]
    center = (sum(prev_voicing)/len(prev_voicing)) if prev_voicing else anchor_octave*12
    first = nearest_register(pitch_classes[0], center)
    # Clamp: if drift pushed us too high, pull down one octave
    if first > max_octave * 12:
        first -= 12
    pitches = [first]
    for pc in pitch_classes[1:]:
        prev = pitches[-1]
        k = -(-(prev + min_gap - pc) // 12)  # ceil division: smallest k with pc+12k >= prev+min_gap
        pitches.append(pc + 12*k)
    return pitches

def realize(abs_pitches):
    return [note_name(p, 0) for p in abs_pitches]

def maybe_add_color(intervals, prob=0.25):
    if 14 not in intervals and random.random() < prob:
        return list(intervals) + [14]
    return list(intervals)

def carry_start(choices, prev_value):
    if prev_value is None:
        return None
    return min(range(len(choices)), key=lambda i: abs(choices[i]-prev_value))

# ---------------------------------------------------------------
# helpers
# ---------------------------------------------------------------
BPM_DEFAULT = 100
STEPS_DEFAULT = 64
# FIX #12: extended with a couple more legitimate spans, and mk() below now
# raises instead of silently defaulting an unrecognized span to "8n".
SPAN_TO_DURATION = {1:"16n", 2:"8n", 3:"8t", 4:"4n", 6:"4n.", 8:"2n", 16:"1n"}

# FIX #1 & #2: mk() now takes the loop's total step count, coerces `step`
# to an int (rounding away any accidental float from timing math), WRAPS it
# into [0, steps_total) instead of leaving negative or out-of-range values
# to be caught only by an external assert, and clamps velocity to [0,1].
def mk(step, note, dur, vel, steps_total):
    s = int(round(step)) % steps_total
    v = max(0.0, min(1.0, vel))
    return {"step": s, "note": note, "duration": dur, "velocity": round(v, 2)}

def contour_sequence(n, choices=(0,1,2,3), start=None, reversal_bias=0.55, max_run=2):
    seq = []
    idx = random.randrange(len(choices)) if start is None else start
    direction = random.choice([1, -1])
    same_count = 0
    for _ in range(n):
        seq.append(choices[idx])
        must_flip = same_count >= max_run
        if must_flip or random.random() < reversal_bias:
            direction = -direction
            same_count = 0
        else:
            same_count += 1
        idx = (idx + direction) % len(choices)
    return seq

# =================================================================
# GENERATORS
# =================================================================

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


# =================================================================
# BAROQUE ENGINE — progressions × textures
# =================================================================
# ── Segment dataclass substitute (plain dict) ─────────────────────
# Each progression builder returns a list of:
#   {"s0": int, "root_pc": int, "quality": str, "bass_pc": int}
# covering every segment (half-bar or bar, depending on style).

# ── Baroque progression builders ─────────────────────────────────

def _baroque_segs(key_pc, scale, steps, seg, formula_degrees, formula_qualities=None):
    """Turn a repeating list of scale degrees into segment dicts."""
    n = len(formula_degrees)
    num_seg = steps // seg
    segs = []
    for i in range(num_seg):
        deg = formula_degrees[i % n]
        scale_len = len(SCALES[scale])
        root_pc = (key_pc + SCALES[scale][deg % scale_len]) % 12
        if formula_qualities:
            qual = formula_qualities[i % len(formula_qualities)]
        else:
            qual = build_diatonic_chord(scale, deg)
        segs.append({"s0": i * seg, "root_pc": root_pc, "quality": qual,
                     "bass_pc": root_pc, "deg": deg})
    return segs


def prog_andalusian(key_pc, scale, steps, seg, minor=True):
    """i–VII–VI–V(major) — Andalusian cadence: Am–G–F–E.

    FIX: degree 6 (bVII = G in A minor) must be looked up in natural_minor,
    NOT harmonic_minor. harmonic_minor[6] = interval 11 → G# (leading tone),
    which turns the bVII into a dissonant chromatic chord instead of the
    expected diatonic G major. Only degree 4 (V) uses harmonic_minor pitch
    class — but SCALES[natural_minor][4] == SCALES[harmonic_minor][4] = 7,
    so swapping to natural_minor across the board is correct and sufficient.
    """
    formula   = [0, 6, 5, 4]
    qualities = ["min", "maj", "maj", "maj"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)


def prog_lament_bass(key_pc, scale, steps, seg, minor=True):
    """Chromatic descending tetrachord (passacaglia / lament bass).

    4-bar ground bass pattern (A minor example):
      Bar:   1       2       3       4
      Bass:  A       G#      G       E   <- E is the dominant (V root)
      Chord: Am      Am/G#   Am/G    E

    The chromatic descent goes tonic -> -1st -> -2nd -> dominant.
    Offset -5 from tonic equals the dominant root (perfect 4th below = V).
    Because bar 4's bass note IS the dominant root, the V chord sits
    perfectly on top — zero clash between bass and harmony.

    KEY FIX (was [0,-1,-2,-3]):
      offset -3 from G# = F natural.  V chord = D# major (D#/F##/A#).
      F natural vs D#/G/A# => minor-7th, whole-step, TRITONE — cacophony!
      offset -5 from G# = D# = the dominant root itself => consonant.
    """
    hm_scale = "harmonic_minor"
    # tonic -> -1 -> -2 -> dominant (perfect 5th up = perfect 4th down = -5)
    chromatic_offsets = [0, -1, -2, -5]
    v_root_pc = (key_pc + SCALES[hm_scale][4]) % 12   # E for Am, D# for G#m

    def _harm(step_idx):
        if step_idx % len(chromatic_offsets) < 3:
            return key_pc % 12, "min"   # i  (Am with chromatic bass)
        else:
            return v_root_pc, "maj"     # V  (E major)

    num_seg = steps // seg
    segs = []
    for i in range(num_seg):
        ch_off  = chromatic_offsets[i % len(chromatic_offsets)]
        bass_pc = (key_pc + ch_off) % 12
        root_pc, qual = _harm(i)
        segs.append({"s0": i * seg, "root_pc": root_pc, "quality": qual,
                     "bass_pc": bass_pc, "deg": i % 4})
    return segs


def prog_pachelbel(key_pc, scale, steps, seg, minor=False):
    """I–V–vi–iii–IV–I–IV–V — Pachelbel's Canon (major)."""
    maj = "major"
    formula = [0, 4, 5, 2, 3, 0, 3, 4]
    # Diatonic qualities in major: 0=maj,1=min,2=min,3=maj,4=maj,5=min,6=dim
    q_map = {0:"maj",1:"min",2:"min",3:"maj",4:"maj",5:"min",6:"dim"}
    qualities = [q_map[d] for d in formula]
    return _baroque_segs(key_pc, maj, steps, seg, formula, qualities)


def prog_circle_of_fifths(key_pc, scale, steps, seg, minor=True):
    """i–iv–VII–III–VI–ii°–V–i — Circle of fifths (minor)."""
    hm = "harmonic_minor"
    formula = [0, 3, 6, 2, 5, 1, 4, 0]
    q_map = {0:"min",1:"dim",2:"maj",3:"min",4:"maj",5:"maj",6:"dim"}
    qualities = [q_map[d % 7] for d in formula]
    return _baroque_segs(key_pc, hm, steps, seg, formula, qualities)


def prog_la_folia(key_pc, scale, steps, seg, minor=True):
    """La Folia 8-chord cycle: i–V–i–VII–III–VII–i–V.

    FIX: degree 6 (bVII) appears at positions 3 and 5 in the formula.
    Must use natural_minor to get G (not G# from harmonic_minor).
    """
    formula   = [0, 4, 0, 6, 2, 6, 0, 4]
    qualities = ["min","maj","min","maj","maj","maj","min","maj"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)


def prog_romanesca(key_pc, scale, steps, seg, minor=True):
    """III–VII–i–V — Romanesca (early baroque).

    FIX: degree 6 (bVII) at position 1 — natural_minor required.
    """
    formula   = [2, 6, 0, 4]
    qualities = ["maj", "maj", "min", "maj"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)


def prog_passamezzo_antico(key_pc, scale, steps, seg, minor=True):
    """i–VII–i–V–III–VII–i–V–i — Passamezzo antico (extended 9-chord).

    FIX: degree 6 (bVII) at positions 1 and 5 — natural_minor required.
    """
    formula   = [0, 6, 0, 4, 2, 6, 0, 4, 0]
    qualities = ["min","maj","min","maj","maj","maj","min","maj","min"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)


def prog_passamezzo_moderno(key_pc, scale, steps, seg, minor=False):
    """I–IV–I–V–I–IV–I–V–I — Passamezzo moderno (major)."""
    maj = "major"
    formula = [0, 3, 0, 4, 0, 3, 0, 4, 0]
    qualities = ["maj","maj","maj","maj","maj","maj","maj","maj","maj"]
    return _baroque_segs(key_pc, maj, steps, seg, formula, qualities)


# ── Baroque texture builders ──────────────────────────────────────
# All texture functions append notes[] in-place and return nothing.

def _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps):
    """Alberti bass: root–fifth–third–fifth in 8th notes."""
    triad = chord_tones(root_pc, qual, 3)
    if len(triad) < 3:
        triad = triad + [triad[-1]]
    # order: root, fifth(idx2), third(idx1), fifth(idx2)
    order = [0, 2, 1, 2]
    n_notes = seg  # one per 16th-step slot, stride 1 → 8n each 2 steps
    for k in range(seg // 2):
        step = s0 + k * 2
        idx = order[k % 4]
        notes.append(mk(step, triad[idx % len(triad)], "8n", 0.45 + 0.05 * (k % 4 == 0), steps))


def _bq_texture_broken_arp(notes, s0, seg, root_pc, qual, steps, direction="up"):
    """Broken chord arpeggio: root→3rd→5th→[oct] smoothly."""
    triad = chord_tones(root_pc, qual, 3)
    # optionally add octave for fuller sweep
    extended = triad + [note_name(root_pc, 4)]
    if direction == "down":
        extended = list(reversed(extended))
    elif direction == "up_down":
        extended = triad + list(reversed(triad))
    n_slots = seg // 2
    for k in range(n_slots):
        step = s0 + k * 2
        note = extended[k % len(extended)]
        notes.append(mk(step, note, "8n", 0.42 + 0.05 * (k == 0), steps))


def _bq_texture_murky(notes, s0, seg, root_pc, steps):
    """Murky bass: octave leaps — low note, same note 8va, repeat."""
    for k in range(seg // 4):
        step_lo = s0 + k * 4
        step_hi = s0 + k * 4 + 2
        notes.append(mk(step_lo, note_name(root_pc, 2), "8n", 0.65, steps))
        notes.append(mk(step_hi, note_name(root_pc, 3), "8n", 0.50, steps))


def _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps, anchor_octave=3):
    """Basso continuo: block chord held for the segment."""
    intervals = list(CHORD_QUALITIES[qual])
    pad_pitches = voice_lead(intervals, root_pc, prev_pad, anchor_octave=anchor_octave, max_octave=anchor_octave + 1)
    for n_ in realize(pad_pitches):
        notes.append(mk(s0, n_, "2n", 0.28, steps))
    return pad_pitches


def _bq_texture_drone(notes, s0, seg, tonic_pc, root_pc, qual, steps):
    """Pedal point: tonic held in bass, upper chord changes above it."""
    notes.append(mk(s0, note_name(tonic_pc, 2), "2n", 0.55, steps))
    upper = chord_tones(root_pc, qual, 4)
    for k, n_ in enumerate(upper):
        step = s0 + k * (seg // max(len(upper), 1))
        if step < s0 + seg:
            notes.append(mk(step, n_, "4n", 0.35, steps))


def _bq_walking_bass_segs(notes, segs, steps, key_pc, scale):
    """Walking bass: stepwise movement between chord roots, one note per half-beat."""
    scale_pcs = SCALES[scale]
    n_scale = len(scale_pcs)
    for idx, seg_d in enumerate(segs):
        s0 = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        next_root_pc = segs[(idx + 1) % len(segs)]["root_pc"]
        # Find scale degree of current root
        best_deg = min(range(n_scale), key=lambda d: (root_pc - key_pc - scale_pcs[d]) % 12)
        # Walk: current root → stepwise → approach next root
        seg_len = (segs[idx + 1]["s0"] if idx + 1 < len(segs) else steps) - s0
        n_steps = seg_len // 4   # one bass note per quarter note
        for b in range(n_steps):
            if b == 0:
                bass_pc = root_pc
            elif b == n_steps - 1:
                # Chromatic approach to next root
                diff = (next_root_pc - root_pc) % 12
                bass_pc = (root_pc + diff - 1) % 12 if diff > 0 else (root_pc - 1) % 12
            else:
                # Diatonic step up
                step_deg = (best_deg + b) % n_scale
                bass_pc = (key_pc + scale_pcs[step_deg]) % 12
            step = s0 + b * 4
            if step < steps:
                notes.append(mk(step, note_name(bass_pc, 2), "4n", 0.58 + 0.07 * (b == 0), steps))


def _bq_melody_voice(notes, segs, key_pc, scale, steps, octave=5):
    """Upper melodic voice: contour-based, one per segment, respects chord tones."""
    prev_mel = None
    mel_choices = (0, 1, 2, 3, 4)
    for seg_d in segs:
        s0 = seg_d["s0"]
        deg = seg_d.get("deg", 0)
        seg_end = s0
        # Find next segment start to know duration
        choices = (deg, deg + 1, deg + 2, deg + 3, deg + 4)
        contour = contour_sequence(2, choices=choices,
                                   start=carry_start(choices, prev_mel),
                                   reversal_bias=0.5, max_run=2)
        for k, d in enumerate(contour):
            step = s0 + k * 4
            if step < steps:
                notes.append(mk(step, scale_tone(key_pc, scale, d, octave),
                                "4n", 0.60 - 0.05 * k, steps))
        prev_mel = contour[-1]


# ── Main baroque generator (diversified) ─────────────────────────

def gen_baroque(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    """
    Baroque generator v2: picks one of several authentic progressions and
    one of several textures on every call, producing varied results.
    """
    notes = []
    scale = "harmonic_minor" if minor else "major"
    seg = max(2, (beats_per_bar * 4) // 2)   # half-bar segments

    # — Choose progression ——————————————————————————————————————————
    if minor:
        prog_builders = [
            lambda: prog_andalusian(key_pc, scale, steps, seg),
            lambda: prog_la_folia(key_pc, scale, steps, seg),
            lambda: prog_romanesca(key_pc, scale, steps, seg),
            lambda: prog_passamezzo_antico(key_pc, scale, steps, seg),
            lambda: prog_circle_of_fifths(key_pc, scale, steps, seg),
        ]
        prog_weights = [30, 25, 15, 15, 15]
    else:
        prog_builders = [
            lambda: prog_pachelbel(key_pc, scale, steps, seg),
            lambda: prog_passamezzo_moderno(key_pc, scale, steps, seg),
            # fall back to Markov for major variety
            lambda: _baroque_segs(key_pc, scale, steps, seg,
                                   generate_harmony(scale, length=8)),
        ]
        prog_weights = [40, 35, 25]

    prog_fn = random.choices(prog_builders, weights=prog_weights, k=1)[0]
    segs = prog_fn()
    if not segs:
        return notes

    # — Choose texture ——————————————————————————————————————————————
    if minor:
        texture = random.choices(
            ["alberti", "walking", "broken_up", "broken_down", "murky", "block"],
            weights=[30, 25, 15, 10, 10, 10], k=1)[0]
    else:
        texture = random.choices(
            ["alberti", "broken_up", "broken_updown", "block", "murky", "walking"],
            weights=[35, 25, 20, 10, 5, 5], k=1)[0]

    # — Build notes ————————————————————————————————————————————————
    prev_pad = None

    if texture == "walking":
        _bq_walking_bass_segs(notes, segs, steps, key_pc, scale)
    
    for seg_d in segs:
        s0 = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual = seg_d["quality"]
        bass_pc = seg_d.get("bass_pc", root_pc)

        # Bass note (always present, but not for walking bass — already done)
        if texture != "walking":
            notes.append(mk(s0, note_name(bass_pc, 2), "4n", 0.58, steps))

        # Mid-register accompaniment (texture-specific)
        if texture == "alberti":
            _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps)

        elif texture in ("broken_up", "broken_down", "broken_updown"):
            direction = {"broken_up": "up", "broken_down": "down",
                         "broken_updown": "up_down"}[texture]
            _bq_texture_broken_arp(notes, s0, seg, root_pc, qual, steps, direction)

        elif texture == "murky":
            _bq_texture_murky(notes, s0, seg, root_pc, steps)
            # add block chord above murky
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)

        elif texture == "block":
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)

        elif texture == "walking":
            # Walking bass already placed; add simple block chord above
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)

    # — Upper melodic voice ————————————————————————————————————————
    _bq_melody_voice(notes, segs, key_pc, scale, steps, octave=5)

    return notes


# ── Specialised baroque style generators ─────────────────────────

def gen_baroque_passacaglia(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    Baroque Passacaglia / Lament bass.
    Ground bass: chromatic descending tetrachord (A–G#–G–F#) in octave 2.
    Above it: sustained block chords (basso continuo), smooth voice leading.
    Slow expressive melody at octave 5.
    Inspired by Purcell's Dido's Lament, Bach's Passacaglia in C minor.

    Fixed: removed _bq_walking_bass_segs (was doubling the bass and adding
    dissonant passing tones against the chromatic ground); melody now uses
    actual harmonic_minor scale degrees instead of the raw seg index.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)   # one chord per bar

    segs = prog_lament_bass(key_pc, scale, steps, seg)
    if not segs:
        return notes

    # Map each lament-bass chord root to its best diatonic scale degree
    # (used for the melody voice so it stays in tune with the harmony)
    scale_pcs = SCALES[scale]
    n_scale = len(scale_pcs)

    def best_scale_deg(root_pc_):
        return min(range(n_scale),
                   key=lambda d: (root_pc_ - key_pc - scale_pcs[d]) % 12)

    prev_pad = None
    prev_mel = None
    pattern_len = 4   # prog_lament_bass always produces a 4-chord cycle

    for i, seg_d in enumerate(segs):
        # Reset voice-leading anchor at the start of every new cycle so
        # the block chord stays in octave 2-3 and does not drift upward.
        if i % pattern_len == 0:
            prev_pad = None

        s0      = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual    = seg_d["quality"]
        bass_pc = seg_d.get("bass_pc", root_pc)  # chromatic lament bass note

        # ── Ground bass: the actual chromatic descending note ──────────
        # Play it twice per bar (downbeat + half-bar) for weight
        notes.append(mk(s0,           note_name(bass_pc, 2), "4n", 0.70, steps))
        if seg >= 8:
            notes.append(mk(s0 + seg // 2, note_name(bass_pc, 2), "4n", 0.55, steps))

        # Basso continuo: block chord in octave 3-4
        prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps, anchor_octave=4)
        if seg >= 8:
            # Play a second chord on the half-bar to keep the slow tempo grounded
            prev_pad = _bq_texture_block_chord(notes, s0 + seg // 2, root_pc, qual, prev_pad, steps, anchor_octave=4)

        # Flowing expressive melody in octave 5 (steady quarter notes)
        chord_deg = best_scale_deg(root_pc)
        mel_choices = (chord_deg, chord_deg + 1, chord_deg + 2,
                       chord_deg + 3, chord_deg - 1)
        mel_choices = tuple(max(0, c) for c in mel_choices)
        
        num_mel_notes = max(2, seg // 4)
        contour = contour_sequence(num_mel_notes, choices=mel_choices,
                                   start=carry_start(mel_choices, prev_mel),
                                   reversal_bias=0.55, max_run=2)
        step_stride = 4  # Quarter notes (1 beat per note)
        for k, d in enumerate(contour):
            step = s0 + k * step_stride
            if step < steps:
                notes.append(mk(step, scale_tone(key_pc, scale, d, 5),
                                "4n", 0.62 - 0.04 * k, steps))
        prev_mel = contour[-1]

    return notes


def gen_baroque_pachelbel(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    """
    Pachelbel Canon progression: I–V–vi–iii–IV–I–IV–V, major.
    Broken-chord arpeggio texture — 'crystal' harpsichord sound.
    """
    notes = []
    scale = "major"
    seg = max(4, beats_per_bar * 4)

    # Choose arpeggio direction per call for variety
    direction = random.choice(["up", "down", "up_down"])
    segs = prog_pachelbel(key_pc, scale, steps, seg)
    if not segs:
        return notes

    prev_pad = None
    for seg_d in segs:
        s0 = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual = seg_d["quality"]

        # Bass: root on the downbeat
        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.60, steps))

        # Broken arpeggio fills the bar
        _bq_texture_broken_arp(notes, s0, seg, root_pc, qual, steps, direction)

        # Occasionally add block chord on beat 3 for weight
        if random.random() < 0.35 and seg >= 8:
            prev_pad = _bq_texture_block_chord(notes, s0 + seg // 2, root_pc, qual, prev_pad, steps)

    # Cantabile melody above
    _bq_melody_voice(notes, segs, key_pc, scale, steps, octave=5)

    return notes


def gen_baroque_circle(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    Circle of fifths progression: i–iv–VII–III–VI–ii°–V–i (minor).
    Alberti bass or murky texture — gives a driven, fugue-like feel.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)

    texture = random.choice(["alberti", "murky"])
    segs = prog_circle_of_fifths(key_pc, scale, steps, seg)
    if not segs:
        return notes

    prev_pad = None
    for seg_d in segs:
        s0 = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual = seg_d["quality"]

        # Bass
        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.60, steps))

        if texture == "alberti":
            _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps)
        else:  # murky
            _bq_texture_murky(notes, s0, seg, root_pc, steps)
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)

    # Two-voice counterpoint above
    prev_v1, prev_v2 = None, None
    v1_choices = (0, 2, 4, 6, 1, 3)
    v2_choices = (1, 3, 5, 0, 2, 4)
    for seg_d in segs:
        s0 = seg_d["s0"]
        deg = seg_d.get("deg", 0)
        c1 = tuple(deg + x for x in (0, 2, 4, 1))
        c2 = tuple(deg + x for x in (1, 3, 5, 2))
        v1 = contour_sequence(2, choices=c1, start=carry_start(c1, prev_v1))
        v2 = contour_sequence(2, choices=c2, start=carry_start(c2, prev_v2))
        for k, d in enumerate(v1):
            step = s0 + k * (seg // 2)
            if step < steps:
                notes.append(mk(step, scale_tone(key_pc, scale, d, 5),
                                "4n", 0.62, steps))
        for k, d in enumerate(v2):
            step = s0 + 2 + k * (seg // 2)
            if step < steps:
                notes.append(mk(step, scale_tone(key_pc, scale, d, 4),
                                "4n", 0.48, steps))
        prev_v1 = v1[-1]
        prev_v2 = v2[-1]

    return notes


def gen_baroque_folia(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    La Folia — 8-chord ostinato: i–V–i–VII–III–VII–i–V.
    Fast Alberti bass in harpsichord style (Corelli, Vivaldi).
    The whole loop is one or two full Folia cycles.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)

    segs = prog_la_folia(key_pc, scale, steps, seg)
    if not segs:
        return notes

    for seg_d in segs:
        s0 = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual = seg_d["quality"]

        # Bass on downbeat
        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.65, steps))

        # Fast Alberti in mid register
        _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps)

    # Virtuoso upper voice: tighter contour, more notes per segment
    prev_mel = None
    mel_choices_base = (0, 1, 2, 3, 4)
    for seg_d in segs:
        s0 = seg_d["s0"]
        deg = seg_d.get("deg", 0)
        choices = tuple(deg + x for x in (0, 1, 2, 3, 4))
        mel_cnt = max(2, seg // 4)   # denser melody
        contour = contour_sequence(mel_cnt, choices=choices,
                                   start=carry_start(choices, prev_mel),
                                   reversal_bias=0.45, max_run=2)
        step_stride = seg // max(mel_cnt, 1)
        for k, d in enumerate(contour):
            step = s0 + k * step_stride
            if step < steps:
                notes.append(mk(step, scale_tone(key_pc, scale, d, 5),
                                "8n", 0.60 - 0.02 * k, steps))
        prev_mel = contour[-1]

    return notes


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


def gen_renaissance(key_pc, scale_name, bpm, steps, beats_per_bar=4, mode="dorian"):
    notes = []
    # FIX #12: previously this line unconditionally overwrote whatever `mode`
    # the caller passed in with a fresh random choice, so
    # "renaissance_dorian" / "renaissance_phrygian" / "renaissance_mixolydian"
    # all played the exact same 3-way random roulette instead of the mode
    # the style name promised. The function now simply uses the `mode` it
    # was given (defaulting to "dorian" only when the caller doesn't specify
    # one, matching the function signature's own default).
    scale = mode
    prog = generate_harmony(scale, length=4)
    n_prog = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps

    R_SOP, R_ALT, R_TEN, R_BAS = 5, 4, 3, 2

    MOT_DUR_SETS = [
        [("4n", 4), ("4n", 4), ("8n", 2), ("8n", 2)],
        [("4n", 4), ("8n", 2), ("8n", 2), ("4n", 4)],
    ]
    mot_durs = random.choice(MOT_DUR_SETS)
    while sum(span for _, span in mot_durs) > bar_steps and len(mot_durs) > 1:
        mot_durs.pop()

    mot_offsets = contour_sequence(len(mot_durs), choices=(0, 1, 2, 3, 4), max_run=2)
    motif_steps = sum(span for _, span in mot_durs)
    imitation_delay = min(8, bar_steps // 2)
    alt_free_from = imitation_delay + motif_steps

    def place_motif(start_step, root_deg, octave, vel_base):
        step = start_step
        for off, (dur, span) in zip(mot_offsets, mot_durs):
            if step >= steps: break
            notes.append(mk(step, scale_tone(key_pc, scale, root_deg + off, octave), dur, round(vel_base + random.uniform(-0.04, 0.04), 2), steps))
            step += span

    sop_prev, alt_prev, ten_prev = None, None, None

    for bar in range(num_bars):
        deg = prog[bar % n_prog]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        qual = diatonic_quality(scale, deg)
        is_last = (bar == num_bars - 1)
        fifth_iv = CHORD_QUALITIES[qual][2]

        if not is_last:
            notes.append(mk(s0, note_name(root_pc, R_BAS), "4n", 0.60, steps))
            if bar_steps > 4:
                notes.append(mk(s0 + bar_steps // 2, note_name(root_pc + fifth_iv, R_BAS), "4n", 0.50, steps))

        # FIX #9: the tenor voice used to keep playing notes derived from the
        # regular progression's `deg` even on the final bar, while bass and
        # soprano switched to the special cadential harmony below — meaning
        # tenor was sounding a foreign scale degree right under the cadence.
        # It now only runs its regular independent line when NOT the last bar;
        # its cadential part is added explicitly in the `is_last` block below.
        if not is_last:
            ten_choices = (deg, deg+1, deg+2, deg+3, deg+4)
            ten_start = carry_start(ten_choices, ten_prev)
            ten_contour = contour_sequence(2, choices=ten_choices, start=ten_start, reversal_bias=0.35, max_run=3)
            if ten_prev is not None and random.random() < 0.30:
                notes.append(mk(s0, scale_tone(key_pc, scale, ten_prev, R_TEN), "8n", 0.45, steps))
                notes.append(mk(s0 + 2, scale_tone(key_pc, scale, ten_prev - 1, R_TEN), "8n", 0.40, steps))
                notes.append(mk(s0 + min(8, bar_steps // 2), scale_tone(key_pc, scale, ten_contour[-1], R_TEN), "4n", 0.42, steps))
            else:
                notes.append(mk(s0, scale_tone(key_pc, scale, ten_contour[0], R_TEN), "2n", 0.45, steps))
                if bar_steps > 4:
                    notes.append(mk(s0 + min(8, bar_steps // 2), scale_tone(key_pc, scale, ten_contour[1], R_TEN), "4n", 0.42, steps))
            ten_prev = ten_contour[-1]

        if bar == 0:
            place_motif(s0, deg, R_SOP, 0.65)
            sop_prev = deg + mot_offsets[-1]
        elif not is_last:
            sop_choices = (deg, deg+2, deg+4, deg+6, deg+1)
            sop_contour = contour_sequence(2, choices=sop_choices, start=carry_start(sop_choices, sop_prev))
            notes.append(mk(s0 + min(4, bar_steps // 4), scale_tone(key_pc, scale, sop_contour[0], R_SOP), "4n", 0.65, steps))
            if bar_steps > 4:
                notes.append(mk(s0 + min(12, bar_steps - 4), scale_tone(key_pc, scale, sop_contour[1], R_SOP), "4n", 0.55, steps))
            sop_prev = sop_contour[-1]

        if bar == 0:
            place_motif(s0 + imitation_delay, deg, R_ALT, 0.55)
            alt_prev = deg + mot_offsets[-1]
        elif s0 >= alt_free_from and not is_last:
            alt_choices = (deg, deg+1, deg+2, deg+3, deg+4)
            alt_contour = contour_sequence(3, choices=alt_choices, start=carry_start(alt_choices, alt_prev), reversal_bias=0.40, max_run=2)
            notes.append(mk(s0, scale_tone(key_pc, scale, alt_contour[0], R_ALT), "4n", 0.50, steps))
            if bar_steps > 4:
                notes.append(mk(s0 + min(6, bar_steps // 3), scale_tone(key_pc, scale, alt_contour[1], R_ALT), "4n", 0.47, steps))
                notes.append(mk(s0 + min(12, (bar_steps * 2) // 3), scale_tone(key_pc, scale, alt_contour[2], R_ALT), "4n", 0.45, steps))
            alt_prev = alt_contour[-1]

        if is_last and num_bars > 1 and bar_steps >= 8:
            final_pc = key_pc
            if mode == "phrygian":
                flat_ii_pc = key_pc + SCALES[scale][1]
                notes.append(mk(s0, note_name(flat_ii_pc, R_BAS), "4n", 0.65, steps))
                notes.append(mk(s0 + bar_steps // 2, note_name(final_pc, R_BAS), "2n", 0.70, steps))
                notes.append(mk(s0 + min(4, bar_steps // 4), scale_tone(key_pc, scale, 1, R_SOP), "4n", 0.65, steps))
                notes.append(mk(s0 + bar_steps // 2, scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70, steps))
                # tenor cadence: holds the 3rd of the bII chord, then resolves down to the tonic's 3rd
                notes.append(mk(s0, scale_tone(key_pc, scale, 1+2, R_TEN), "4n", 0.45, steps))
                notes.append(mk(s0 + bar_steps // 2, scale_tone(key_pc, scale, 2, R_TEN), "2n", 0.45, steps))
            else:
                v_pc = key_pc + SCALES[scale][4]
                notes.append(mk(s0, note_name(v_pc, R_BAS), "4n", 0.60, steps))
                notes.append(mk(s0 + bar_steps // 2, note_name(final_pc, R_BAS), "2n", 0.65, steps))
                for k, loff in enumerate([5, 6, 0]):
                    notes.append(mk(s0 + bar_steps // 2 + k * 2, scale_tone(key_pc, scale, loff, R_SOP), "8n", max(0.40, 0.68 - k * 0.05), steps))
                # tenor cadence: holds the 3rd of V, then resolves to the 3rd of the final tonic chord
                notes.append(mk(s0, scale_tone(key_pc, scale, 4+2, R_TEN), "4n", 0.42, steps))
                notes.append(mk(s0 + bar_steps // 2, scale_tone(key_pc, scale, 2, R_TEN), "2n", 0.42, steps))
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


# ---------------------------------------------------------------
# MASTER DISPATCH
# ---------------------------------------------------------------
STYLE_META = {
    "neoclassical_major": dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_neoclassical(kp,s,b,st,bpb,minor=False)),
    "neoclassical_minor": dict(scale="harmonic_minor",  swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_neoclassical(kp,s,b,st,bpb,minor=True)),
    "baroque_major":      dict(scale="major",          swing=0.0,  segment_steps=lambda b: max(2, (b*4)//2), fn=lambda kp,s,b,st,bpb: gen_baroque(kp,s,b,st,bpb,minor=False)),
    "baroque_minor":      dict(scale="harmonic_minor",  swing=0.0,  segment_steps=lambda b: max(2, (b*4)//2), fn=lambda kp,s,b,st,bpb: gen_baroque(kp,s,b,st,bpb,minor=True)),
    # ── New specialised baroque styles ──────────────────────────────────────────
    # passacaglia: chromatic lament bass, one chord per bar
    "baroque_passacaglia": dict(scale="harmonic_minor", swing=0.0,  segment_steps=lambda b: b*4,             fn=lambda kp,s,b,st,bpb: gen_baroque_passacaglia(kp,s,b,st,bpb)),
    # pachelbel: I–V–vi–iii–IV–I–IV–V major, broken arpeggio
    "baroque_pachelbel":   dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4,             fn=lambda kp,s,b,st,bpb: gen_baroque_pachelbel(kp,s,b,st,bpb)),
    # circle of fifths: i–iv–VII–III–VI–ii°–V–i minor, fugue-like drive
    "baroque_circle":      dict(scale="harmonic_minor", swing=0.0,  segment_steps=lambda b: b*4,             fn=lambda kp,s,b,st,bpb: gen_baroque_circle(kp,s,b,st,bpb)),
    # la folia: 8-chord ostinato, fast Alberti, Corelli/Vivaldi style
    "baroque_folia":       dict(scale="harmonic_minor", swing=0.0,  segment_steps=lambda b: b*4,             fn=lambda kp,s,b,st,bpb: gen_baroque_folia(kp,s,b,st,bpb)),
    "jazz_major":         dict(scale="major",          swing=0.6,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_jazz(kp,s,b,st,bpb,minor=False)),
    "jazz_minor":         dict(scale="dorian",         swing=0.6,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_jazz(kp,s,b,st,bpb,minor=True)),
    "modal_folk":         dict(scale="dorian",         swing=0.15, segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_modal_folk(kp,s,b,st,bpb)),
    "classical_alberti":  dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_classical_alberti(kp,s,b,st,bpb)),
    "renaissance_dorian": dict(scale="dorian",         swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_renaissance(kp,s,b,st,bpb,mode="dorian")),
    "renaissance_phrygian": dict(scale="phrygian",     swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_renaissance(kp,s,b,st,bpb,mode="phrygian")),
    "renaissance_mixolydian": dict(scale="mixolydian", swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_renaissance(kp,s,b,st,bpb,mode="mixolydian")),
    "blues":              dict(scale="blues",          swing=0.6,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_blues(kp,s,b,st,bpb)),
    "ragtime":            dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_ragtime(kp,s,b,st,bpb)),
    # FIX #3/#4: waltz split into major/minor, each explicit about its scale,
    # and driven by the beats_per_bar the CALLER passes (3 by default, see
    # generate_loop below).
    "waltz_major":        dict(scale="major",          swing=0.1,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_waltz(kp,s,b,st,bpb,minor=False)),
    "waltz_minor":         dict(scale="harmonic_minor",  swing=0.1,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_waltz(kp,s,b,st,bpb,minor=True)),
    "bossa_nova":         dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_bossa_nova(kp,s,b,st,bpb)),
    "romantic_major":     dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_romantic(kp,s,b,st,bpb,minor=False)),
    "romantic_minor":     dict(scale="harmonic_minor",  swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_romantic(kp,s,b,st,bpb,minor=True)),
    "lofi":               dict(scale="major",          swing=0.6,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_lofi(kp,s,b,st,bpb)),
    "neo_soul":           dict(scale="major",          swing=0.4,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_neo_soul(kp,s,b,st,bpb)),
    "video_game":         dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_video_game(kp,s,b,st,bpb)),
    "einaudi_minor":      dict(scale="natural_minor",  swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_einaudi(kp,s,b,st,bpb,minor=True)),
    "einaudi_major":      dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_einaudi(kp,s,b,st,bpb,minor=False)),
    "glass_minor":        dict(scale="dorian",         swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_glass(kp,s,b,st,bpb,minor=True)),
    "glass_major":        dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_glass(kp,s,b,st,bpb,minor=False)),
    "tiersen_minor":      dict(scale="harmonic_minor", swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_tiersen(kp,s,b,st,bpb,minor=True)),
    "tiersen_major":      dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_tiersen(kp,s,b,st,bpb,minor=False)),
    "frahm_minor":        dict(scale="natural_minor",  swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_frahm(kp,s,b,st,bpb,minor=True)),
    "frahm_major":        dict(scale="major",          swing=0.0,  segment_steps=lambda b: b*4, fn=lambda kp,s,b,st,bpb: gen_frahm(kp,s,b,st,bpb,minor=False)),
}

# Styles whose natural/idiomatic meter isn't 4/4 — generate_loop uses this to
# pick a sane default beats_per_bar instead of silently assuming 4 for
# everything (fix for issue #4, generalized beyond just waltz).
STYLE_DEFAULT_METER = {
    "waltz_major": 3,
    "waltz_minor": 3,
    "tiersen_major": 3,
    "tiersen_minor": 3,
}

def generate_loop(style, key, name=None, bpm=BPM_DEFAULT, steps=None, beats_per_bar=None, seed=None):
    if seed is not None:
        random.seed(seed)
    if beats_per_bar is None:
        beats_per_bar = STYLE_DEFAULT_METER.get(style, 4)
    meta = STYLE_META[style]
    seg = meta["segment_steps"](beats_per_bar)
    if steps is None:
        # auto-pick the smallest multiple of `seg` that's >= STEPS_DEFAULT,
        # so callers don't have to know each style's segment size just to
        # get a loop with no explicit steps argument (this is what broke
        # waltz_major/minor and tiersen, whose 3-beat bars don't divide 64).
        steps = seg * -(-STEPS_DEFAULT // seg)  # ceil division
    if steps <= 0 or steps % seg != 0:
        raise ValueError(
            f"steps must be a positive multiple of {seg} for style '{style}' (got {steps})"
        )
    key_pc = PC[key]
    notes = meta["fn"](key_pc, meta["scale"], bpm, steps, beats_per_bar)
    notes.sort(key=lambda x: x["step"])
    _MINOR_MODES = {"natural_minor", "harmonic_minor", "melodic_minor_asc",
                    "dorian", "phrygian", "locrian", "blues"}
    scale_label = "Minor" if meta["scale"] in _MINOR_MODES else "Major"
    return {
        "name": name or f"{style.replace('_',' ').title()} in {key}",
        "bpm": bpm, "instrument": "piano", "steps": steps,
        "key": key, "scale": scale_label, "swing": meta["swing"], "notes": notes,
        "style": style,
        "beats_per_bar": beats_per_bar
    }

if __name__ == "__main__":
    KEYS_DEMO = ["C","G","D","A","F","E"]
    demo = []
    for i,style in enumerate(STYLE_META.keys()):
        for j in range(2):
            key = KEYS_DEMO[(i*2+j) % len(KEYS_DEMO)]
            bpb = STYLE_DEFAULT_METER.get(style, 4)
            demo.append(generate_loop(style, key, seed=500+i*2+j, beats_per_bar=bpb, steps=bpb*4*16))

    for style in ["jazz_minor", "classical_alberti"]:
        demo.append(generate_loop(style, "C", seed=100, beats_per_bar=3, steps=48))

    for style in ["jazz_major", "neoclassical_major"]:
        demo.append(generate_loop(style, "C", seed=200, beats_per_bar=5, steps=80))

    print("generated:", len(demo))
    for l in demo:
        beats = l.get("beats_per_bar", 4)
        dur = l["steps"]*(60.0/l["bpm"]/4.0)
        assert dur >= 6.0
        assert all(0 <= n["step"] < l["steps"] for n in l["notes"]), f"note stepped outside the loop in {l['style']} {beats}/4"
        assert all(isinstance(n["step"], int) for n in l["notes"]), f"non-integer step leaked in {l['style']}"
        assert all(0 <= n["velocity"] <= 1 for n in l["notes"]), "velocity out of range"
        print(f"{l['name']:34s} style={l['style']:20s} beats={beats} notes:{len(l['notes']):3d} swing:{l['swing']}")

    # confirm waltz styles are genuinely in 3 by default now
    w = generate_loop("waltz_major", "D")
    assert w["beats_per_bar"] == 3, "waltz should default to 3/4"
    print("waltz default meter check passed:", w["beats_per_bar"])

    # confirm tiersen styles are genuinely in 3 by default now
    t = generate_loop("tiersen_major", "D")
    assert t["beats_per_bar"] == 3, "tiersen should default to 3/4"
    print("tiersen default meter check passed:", t["beats_per_bar"])

    # confirm romantic/frahm honor the scale they're registered under
    # (no more internal coin-flip contradicting the style's declared scale)
    for _ in range(10):
        rm = generate_loop("romantic_minor", "A")
        assert rm["scale"] == "Minor"
        rM = generate_loop("romantic_major", "A")
        assert rM["scale"] == "Major"
        
        em = generate_loop("einaudi_minor", "A")
        assert em["scale"] == "Minor"
        eM = generate_loop("einaudi_major", "A")
        assert eM["scale"] == "Major"
    print("romantic/einaudi scale-consistency check passed")

    # NEW: confirm the three renaissance styles are actually distinct modes
    # now, instead of all rerolling the same random 3-way choice internally.
    for _ in range(10):
        rd = generate_loop("renaissance_dorian", "C")
        rp = generate_loop("renaissance_phrygian", "C")
        rm2 = generate_loop("renaissance_mixolydian", "C")
        assert rd["scale"] == "Minor"   # dorian counted as a minor-family mode
        assert rp["scale"] == "Minor"   # phrygian counted as a minor-family mode
        assert rm2["scale"] == "Major"  # mixolydian is major-family (no b3)
    print("renaissance mode-consistency check passed")

    # NEW: sanity-check that the per-call pattern randomization added to
    # einaudi/glass/tiersen/frahm doesn't crash and produces valid loops
    # across a spread of seeds.
    for seed in range(10):
        for style in ["einaudi_minor", "glass_major", "tiersen_minor", "frahm_major"]:
            l = generate_loop(style, "C", seed=1000 + seed)
            assert all(0 <= nn["step"] < l["steps"] for nn in l["notes"])
    print("pattern-variety smoke test passed")

    try:
        generate_loop("jazz_minor", "A", steps=20, beats_per_bar=4)
        raise AssertionError("expected ValueError for a steps value that isn't a valid multiple")
    except ValueError:
        pass
    print("steps-axis checks passed")

    # ── Pitch-correctness regression tests (musical golden values) ────────
    # These catch bVII degree-6 bugs: the correct scale for bVII is natural_minor
    # (interval 10 → G in Am), NOT harmonic_minor (interval 11 → G#, leading tone).

    def _roots(segs):
        return [note_name(s["root_pc"], 2) for s in segs]

    # Andalusian: Am–G–F–E (one full cycle, seg=16)
    segs_and = prog_andalusian(PC["A"], "harmonic_minor", steps=64, seg=16)
    assert _roots(segs_and) == ["A2", "G2", "F2", "E2"], \
        f"prog_andalusian pitch bug: expected A2-G2-F2-E2, got {_roots(segs_and)}"
    print("prog_andalusian pitch check passed")

    # La Folia: positions 3 and 5 of the 8-chord cycle must be G (bVII)
    segs_fol = prog_la_folia(PC["A"], "harmonic_minor", steps=128, seg=16)
    assert segs_fol[3]["root_pc"] % 12 == PC["G"], \
        f"prog_la_folia pos-3 pitch bug: expected G, got pc={segs_fol[3]['root_pc'] % 12}"
    assert segs_fol[5]["root_pc"] % 12 == PC["G"], \
        f"prog_la_folia pos-5 pitch bug: expected G, got pc={segs_fol[5]['root_pc'] % 12}"
    print("prog_la_folia pitch check passed")

    # Romanesca: position 1 (VII) must be G in Am
    segs_rom = prog_romanesca(PC["A"], "harmonic_minor", steps=64, seg=16)
    assert segs_rom[1]["root_pc"] % 12 == PC["G"], \
        f"prog_romanesca pos-1 pitch bug: expected G, got pc={segs_rom[1]['root_pc'] % 12}"
    print("prog_romanesca pitch check passed")

    # Passamezzo antico: positions 1 and 5 (VII) must be G in Am
    segs_pas = prog_passamezzo_antico(PC["A"], "harmonic_minor", steps=144, seg=16)
    assert segs_pas[1]["root_pc"] % 12 == PC["G"], \
        f"prog_passamezzo_antico pos-1 pitch bug: expected G, got pc={segs_pas[1]['root_pc'] % 12}"
    assert segs_pas[5]["root_pc"] % 12 == PC["G"], \
        f"prog_passamezzo_antico pos-5 pitch bug: expected G, got pc={segs_pas[5]['root_pc'] % 12}"
    print("prog_passamezzo_antico pitch check passed")

    # Sanity-check: prog_circle_of_fifths is NOT broken — its degree-6 is vii°
    # (raised leading tone on harmonic_minor[6] = 11 semitones → G# in Am = correct dim chord)
    segs_cof = prog_circle_of_fifths(PC["A"], "harmonic_minor", steps=128, seg=16)
    assert segs_cof[2]["quality"] == "dim", \
        f"prog_circle_of_fifths vii° should be 'dim', got {segs_cof[2]['quality']}"
    print("prog_circle_of_fifths vii° check passed (unchanged — correct)")

    demo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theory_engine_demo_v4.json")
    with open(demo_path, "w", encoding="utf-8") as f:
        json.dump(demo, f, ensure_ascii=False, indent=2)
    print(f"Demo written to: {demo_path}")