"""
PARAMETRIC MUSIC THEORY ENGINE
================================
generate_loop(style, key, bpm, steps) -> loop dict matching the sequencer JSON schema.

Six axes modeled explicitly: scale, chord vocabulary, progression grammar,
rhythm/meter, texture, ornamentation. Plus two layers that exist specifically
to make repeated generations sound like different pieces of music instead of
the same skeleton with different notes on top:

  - VARIETY POOLS: every style now picks from several progressions (and,
    where it matters stylistically, alternate rhythmic/melodic templates)
    once per generate_loop() call, instead of having exactly one hardcoded
    shape. Two loops, same style, same key, different seed -> structurally
    different pieces.

  - VOICE LEADING: chord "pad"/"comping" blocks are realized in the octave
    closest to the previous chord's center of gravity (common tones held,
    other voices move by step) instead of transposing the whole chord in
    lockstep from bar to bar -- which is literally parallel fifths/octaves.

  - CONTINUITY: melodic/arpeggio contours pick up near where the previous
    bar left off instead of re-rolling a fresh random register every bar.

Chord qualities for plain diatonic styles (baroque, modal folk, classical
Alberti) are DERIVED from the scale, not hand-typed -- this is what caught
a real error while writing this: a hand-typed "min7" for a Dorian iv chord
turned out to actually be a dominant 7th once the intervals were computed.
Deriving it programmatically removes that whole class of mistake.

`steps` is a real axis: every generator cycles its progression to fill
however many bars fit. Must be a positive multiple of the style's bar
length (16, or 8 for baroque) -- ValueError otherwise, no silent wrapping.
"""
import json, os, random

NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
PC = {n:i for i,n in enumerate(NOTE_NAMES)}

def note_name(semitone, octave):
    idx = semitone % 12
    octv = octave + semitone // 12
    return f"{NOTE_NAMES[idx]}{octv}"

# ---------------------------------------------------------------
# AXIS 1: SCALES / MODES (semitone offsets from tonic)
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
    """degree can exceed len(scale)-1 or be negative — wraps across octaves."""
    scale = SCALES[scale_name]
    n = len(scale)
    octv_add, d = divmod(degree, n)
    return note_name(key_pc + scale[d], octave + octv_add)

def _degree_pc(scale_name, degree):
    """Correctly octave-wrapped pitch class for a scale degree that may
    exceed the scale length (e.g. degree+6 for a diatonic 7th). This wrap
    logic is exactly what gen_jazz's old third_iv bug was missing."""
    scale = SCALES[scale_name]
    n = len(scale)
    octv_add, idx = divmod(degree, n)
    return scale[idx] + 12*octv_add

def diatonic_quality(scale_name, degree):
    """The triad quality that actually results from stacking thirds within
    the given scale at this degree — computed, not guessed."""
    root = _degree_pc(scale_name, degree)
    third = _degree_pc(scale_name, degree+2) - root
    fifth = _degree_pc(scale_name, degree+4) - root
    if (third,fifth) == (4,7): return "maj"
    if (third,fifth) == (3,7): return "min"
    if (third,fifth) == (3,6): return "dim"
    if (third,fifth) == (4,8): return "aug"
    return "maj"  # defensive fallback, shouldn't trigger for standard 7-note scales

SEVENTH_QUALITY_MAP = {
    (4,7,11): "maj7",
    (3,7,10): "min7",
    (4,7,10): "dom7",
    (3,6,10): "m7b5",
}

def diatonic_seventh(scale_name, degree):
    """The 7th-chord quality that actually results from stacking thirds
    within the given scale at this degree."""
    root = _degree_pc(scale_name, degree)
    third = _degree_pc(scale_name, degree+2) - root
    fifth = _degree_pc(scale_name, degree+4) - root
    seventh = _degree_pc(scale_name, degree+6) - root
    return SEVENTH_QUALITY_MAP.get((third,fifth,seventh), "dom7")

def build_diatonic_chord(scale_name, degree, force_dominant7=True):
    """Diatonic triad, with the true dominant (scale degree V) optionally
    upgraded to a dominant 7th for cadential strength."""
    quality = diatonic_quality(scale_name, degree)
    if force_dominant7 and degree % len(SCALES[scale_name]) == 4 and quality == "maj":
        return "dom7"
    return quality

def extend_dominant(quality, prob=0.5):
    """Occasionally color a dominant 7th up to a dominant 9th. Doesn't
    change the chord's function, just its flavor."""
    if quality == "dom7" and random.random() < prob:
        return "dom9"
    return quality

# ---------------------------------------------------------------
# AXIS 2: CHORD VOCABULARY
# All qualities have >=3 intervals: index 0=root, 1=third, 2=fifth, 3=seventh.
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
    "dom9":  [0,4,7,10,14],
    "min9":  [0,3,7,10,14],
    "maj9":  [0,4,7,11,14],
}

def chord_tones(root_pc, quality, octave):
    return [note_name(root_pc+iv, octave) for iv in CHORD_QUALITIES[quality]]

def shell_intervals(quality):
    """Root + 3rd + 7th (drop the 5th) for jazz comping — idiomatic 'shell'
    voicing. Falls back to the full triad for plain (non-seventh) chords."""
    ivs = CHORD_QUALITIES[quality]
    return [ivs[0], ivs[1], ivs[3]] if len(ivs) >= 4 else list(ivs)

# ---------------------------------------------------------------
# VOICE LEADING for block chords (pad / comping): realize each pitch class
# in the octave closest to the previous chord's center of gravity, instead
# of transposing the whole chord in lockstep (which produces parallel
# fifths/octaves between every pair of voices whenever the root moves).
# ---------------------------------------------------------------
def nearest_register(pc, center):
    k = round((center - pc) / 12)
    return pc + 12*k

def voice_lead(intervals, root_pc, prev_voicing, anchor_octave=4):
    pitch_classes = [(root_pc + iv) % 12 for iv in intervals]
    center = (sum(prev_voicing)/len(prev_voicing)) if prev_voicing else anchor_octave*12
    return sorted(nearest_register(pc, center) for pc in pitch_classes)

def realize(abs_pitches):
    return [note_name(p, 0) for p in abs_pitches]

def maybe_add_color(intervals, prob=0.25):
    """Occasionally add the 9th as a color tone without changing the
    chord's harmonic function."""
    if 14 not in intervals and random.random() < prob:
        return list(intervals) + [14]
    return list(intervals)

# ---------------------------------------------------------------
# CONTINUITY for melodic/arpeggio contours
# ---------------------------------------------------------------
def carry_start(choices, prev_value):
    """Index into `choices` closest to prev_value, so a new bar's contour
    picks up near where the last one left off instead of re-rolling a
    fresh random register. None (no previous value yet) -> fresh random
    start, same as before."""
    if prev_value is None:
        return None
    return min(range(len(choices)), key=lambda i: abs(choices[i]-prev_value))

# ---------------------------------------------------------------
# helpers
# ---------------------------------------------------------------
BPM_DEFAULT = 100
STEPS_DEFAULT = 64
BAR_STEPS = 16                  # one bar = 16 sixteenth-note steps (4/4)
BAROQUE_SEGMENT_STEPS = 8       # baroque changes harmony every half-bar
SPAN_TO_DURATION = {1:"16n", 2:"8n", 4:"4n", 8:"2n", 16:"1n"}

def mk(step, note, dur, vel):
    return {"step": step, "note": note, "duration": dur, "velocity": round(vel,2)}

def contour_sequence(n, choices=(0,1,2,3), start=None, reversal_bias=0.55, max_run=2):
    """
    Generates an index sequence into `choices` that genuinely goes up AND down —
    not a fixed ascending cycle. Direction flips probabilistically, and is FORCED
    to flip after `max_run` consecutive steps in the same direction, so you never
    get a long monotonic ramp (the "up-up-up-up" problem).
    """
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
# STYLE 1 — NEOCLASSICAL (major or minor), homophony:
#   sustained bass + arpeggio + pentatonic-ish melody line
# =================================================================
def gen_neoclassical(key_pc, scale_name, bpm, steps, minor=False):
    notes = []
    scale = "harmonic_minor" if minor else "major"

    major_progs = [
        ([0,5,3,4], ["maj","min","maj","maj"]),   # I-vi-IV-V
        ([0,4,5,3], ["maj","maj","min","maj"]),   # I-V-vi-IV
        ([5,0,3,4], ["min","maj","maj","maj"]),   # vi-I-IV-V
        ([0,3,4,3], ["maj","maj","maj","maj"]),   # I-IV-V-IV
        ([0,2,5,4], ["maj","min","min","maj"]),   # I-iii-vi-V
        ([5,3,4,0], ["min","maj","maj","maj"]),   # vi-IV-V-I
    ]
    minor_progs = [
        ([0,5,2,4], ["min","maj","aug","dom7"]),  # i-VI-III⁺-V7  (III augmented in harmonic minor)
        ([0,3,4,0], ["min","min","maj","min"]),   # i-iv-V-i
        ([5,3,0,4], ["maj","min","min","dom7"]),  # VI-iv-i-V7
        ([0,6,5,4], ["min","dim","maj","dom7"]),  # i-vii°-VI-V7
    ]
    degrees, qualities = random.choice(minor_progs if minor else major_progs)
    n = len(degrees)
    num_bars = steps // BAR_STEPS

    arp_notes_per_bar = random.choice([4, 8])   # density variety, chosen once per loop
    step_span = BAR_STEPS // arp_notes_per_bar
    arp_dur = SPAN_TO_DURATION[step_span]

    prev_arp_val = None
    prev_mel_val = None

    for bar in range(num_bars):
        deg, qual = degrees[bar % n], qualities[bar % n]
        bar_start = bar*BAR_STEPS
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        chord = chord_tones(root_pc, qual, 3) + [note_name(root_pc,4)]
        notes.append(mk(bar_start, note_name(root_pc,2), "1n", 0.65))

        arp_choices = tuple(range(len(chord)))
        arp_idx = contour_sequence(arp_notes_per_bar, choices=arp_choices,
                                    start=carry_start(arp_choices, prev_arp_val))
        for i,ci in enumerate(arp_idx):
            note = chord[ci]
            notes.append(mk(bar_start+i*step_span, note, arp_dur, 0.35+random.uniform(0,0.2)))
        prev_arp_val = arp_idx[-1]

        # mel_choices in ABSOLUTE scale-degree space (same units as prev_mel_val),
        # so carry_start compares old and new notes in a stable coordinate system
        # regardless of how far the chord root shifts between bars.
        # On the first bar carry_start returns None → contour_sequence picks a
        # fresh random start, which is exactly the right behaviour.
        mel_choices = (deg, deg+2, deg+4, deg+6, deg+1)
        mel_contour = contour_sequence(2, choices=mel_choices,
                                       start=carry_start(mel_choices, prev_mel_val))
        notes.append(mk(bar_start+6,  scale_tone(key_pc, scale, mel_contour[0], 5), "4n", 0.65))
        notes.append(mk(bar_start+12, scale_tone(key_pc, scale, mel_contour[1], 5), "4n", 0.55))
        prev_mel_val = mel_contour[-1]
    return notes


# =================================================================
# STYLE 2 — BAROQUE, polyphony:
#   circle-of-fifths-family sequence (root motion picked from a pool,
#   quality DERIVED from the scale, V auto-upgraded to V7) + voice-led
#   pad + independent upper voice with cross-segment continuity + a
#   trill ornament at the cadence
#
#   INVARIANT: steps must be a positive multiple of BAROQUE_SEGMENT_STEPS (8).
#   generate_loop() enforces this via ValueError before calling this function,
#   so num_segments is always an exact integer — no silent bar loss.
# =================================================================
def gen_baroque(key_pc, scale_name, bpm, steps, minor=False):
    notes = []
    scale = "harmonic_minor" if minor else "major"

    major_seqs = [
        [0,3,6,2,5,1,4,0],   # I-IV-vii°-iii-vi-ii-V-I (classic descending-fifths)
        [0,5,1,4,0,3,6,2],   # I-vi-ii-V-I-IV-vii°-iii
        [0,4,5,2,3,0,3,4],   # I-V-vi-iii-IV-I-IV-V (Pachelbel-family)
    ]
    minor_seqs = [
        [0,3,6,2,5,1,4,0],
        [0,4,0,3,6,1,4,0],
        [5,3,0,4,0,3,4,0],
    ]
    seq_degrees = random.choice(minor_seqs if minor else major_seqs)
    n = len(seq_degrees)
    seg = BAROQUE_SEGMENT_STEPS
    num_segments = steps // seg

    prev_pad = None
    prev_v2_val = None

    for i in range(num_segments):
        deg = seq_degrees[i % n]
        qual = build_diatonic_chord(scale, deg)
        s0 = i*seg
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        # BASS: clean harmonic pulse (root, then 5th) — anchors the chord
        notes.append(mk(s0,   note_name(root_pc,2), "4n", 0.55))
        notes.append(mk(s0+4, note_name(root_pc+CHORD_QUALITIES[qual][2], 2), "4n", 0.45))

        # CHORD PAD: voice-led, not block-transposed — common tones held,
        # everything else moves by the smallest possible step
        pad_intervals = maybe_add_color(CHORD_QUALITIES[qual])
        pad_pitches = voice_lead(pad_intervals, root_pc, prev_pad, anchor_octave=4)
        for note in realize(pad_pitches):
            notes.append(mk(s0, note, "2n", 0.25))
        prev_pad = pad_pitches

        # VOICE 2 (upper melodic line): independent contour, continues from
        # where the previous segment left off
        chord = chord_tones(root_pc, qual, 5)
        v2_choices = tuple(range(len(chord)))
        v2_idx = contour_sequence(4, choices=v2_choices, start=carry_start(v2_choices, prev_v2_val))
        for j2,ci in zip(range(0, seg, 2), v2_idx):
            step = s0+j2
            note = chord[ci]
            notes.append(mk(step, note, "8n", 0.55+0.05*(j2%4==0)))
        prev_v2_val = v2_idx[-1]

        # cadence ornament: a trill on the final chord of the actual loop
        if i == num_segments-1:
            for k in range(4):
                t_step = s0 + seg - 4 + k
                trill_note = note_name(root_pc + (2 if k%2==0 else 0), 5)
                notes.append(mk(t_step, trill_note, "32n", 0.6))
    return notes


# =================================================================
# STYLE 3 — JAZZ:
#   functional ii-V-I family (major: quality DERIVED from the scale, since
#   major's own diatonic 7ths already give exactly ii=min7/V=dom7/I=maj7 —
#   no borrowing needed) vs minor ii-V-i (quality hand-specified, because
#   the idiomatic minor ii-V-i borrows m7b5/altered-dominant qualities that
#   Dorian's own diatonic 7ths do NOT produce — verified by computing them,
#   not assumed), WALKING BASS, shell-voiced comping (root-3rd-7th, voice-led),
#   swung eighths, and a blue note
# =================================================================
def gen_jazz(key_pc, scale_name, bpm, steps, minor=False):
    notes = []
    if minor:
        scale = "dorian"
        progs = [
            [(1,"m7b5"), (4,"dom7"), (0,"min7"), (5,"dom7")],   # ii°-V-i-[V7/ii turnaround]
            [(1,"m7b5"), (4,"dom7"), (0,"min7"), (3,"min7")],   # ii°-V-i-iv
            [(0,"min7"), (3,"min7"), (5,"maj7"), (4,"dom7")],   # i-iv-VI-V
        ]
        prog = random.choice(progs)
    else:
        scale = "major"
        degree_progs = [
            [1,4,0,0],   # ii-V-I-I
            [2,5,1,4],   # iii-vi-ii-V
            [0,5,1,4],   # I-vi-ii-V
        ]
        degrees = random.choice(degree_progs)
        prog = [(deg, extend_dominant(diatonic_seventh(scale, deg))) for deg in degrees]

    n = len(prog)
    bar_len = BAR_STEPS
    num_bars = steps // bar_len

    prev_comp = None
    prev_mel_val = None

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar*bar_len
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        # COMPING: shell voicing (root-3rd-7th, drop the 5th), voice-led so
        # it doesn't just block-transpose from chord to chord
        comp_intervals = maybe_add_color(shell_intervals(qual), prob=0.2)
        comp_pitches = voice_lead(comp_intervals, root_pc, prev_comp, anchor_octave=3)
        comp_names = realize(comp_pitches)
        prev_comp = comp_pitches

        # WALKING BASS stays strictly in its own low register (octave 2 only).
        # "next chord" = whatever bar the loop actually plays next (respects
        # a shorter/longer requested loop length, not just the raw cycle length).
        next_bar = (bar+1) % num_bars
        next_deg = prog[next_bar % n][0]
        next_root_pc = key_pc + SCALES[scale][next_deg % len(SCALES[scale])]
        third_iv = CHORD_QUALITIES[qual][1]   # chromatic interval from the chord itself —
        fifth_iv = CHORD_QUALITIES[qual][2]   # not a diatonic scale-degree lookup (that's what broke before)
        walk = [root_pc, root_pc+third_iv, root_pc+fifth_iv, next_root_pc-1]
        for b,pc_ in enumerate(walk):
            notes.append(mk(s0+b*4, note_name(pc_,2), "4n", 0.6+0.05*(b==0)))

        # Comping stabs on the off-beats, own register, separated from bass
        for off in [6,14]:
            for note in comp_names:
                notes.append(mk(s0+off, note, "8n", 0.35))

        # melody: real up/down contour, continues from where the previous
        # bar left off, own register (octave 5)
        mel_chord = chord_tones(root_pc, qual, 5)
        mel_choices = (0,1,2,3) if len(mel_chord)>3 else (0,1,2)
        mel_idx = contour_sequence(6, choices=mel_choices, start=carry_start(mel_choices, prev_mel_val))
        for i,ci in enumerate(mel_idx):
            step = s0 + 2 + i*2
            if step >= s0+bar_len: continue
            note = mel_chord[ci % len(mel_chord)]
            notes.append(mk(step, note, "8n", 0.5+random.uniform(0,0.15)))
        prev_mel_val = mel_idx[-1]
        if bar % n == 1:
            blue = note_name(root_pc+3, 5)
            notes.append(mk(s0+10, blue, "16n", 0.55))
    return notes


# =================================================================
# STYLE 4 — MODAL FOLK (Dorian):
#   static modal vamp (no functional cadence — that's the point of modal
#   writing; quality derived from the scale, no forced V7), drone bass,
#   voice-led chord pad, melody built from a pool of shapes
# =================================================================
def gen_modal_folk(key_pc, scale_name, bpm, steps):
    notes = []
    scale = "dorian"
    prog_pool = [
        [0,3,0,3],   # i-IV-i-IV
        [0,3,6,0],   # i-IV-bVII-i
        [0,6,3,0],   # i-bVII-IV-i
    ]
    prog = random.choice(prog_pool)
    n = len(prog)
    bar_len = BAR_STEPS
    num_bars = steps // bar_len

    # relative scale-degree offsets from each bar's chord root, spanning
    # roughly an octave of the mode — a real contour, not a fixed shape,
    # so two loops in the same key/style no longer share a melody.
    mel_choices = (0,1,2,3,4,5)

    prev_pad = None
    prev_mel_val = None
    for bar in range(num_bars):
        deg = prog[bar % n]
        s0 = bar*bar_len
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        notes.append(mk(s0, note_name(key_pc,2), "1n", 0.5))  # DRONE stays on the tonic regardless of chord above

        qual = diatonic_quality(scale, deg)
        pad_pitches = voice_lead(CHORD_QUALITIES[qual], root_pc, prev_pad, anchor_octave=4)
        for note in realize(pad_pitches):
            notes.append(mk(s0+8, note, "2n", 0.3))
        prev_pad = pad_pitches

        # lower reversal_bias / higher max_run than the default contour, for
        # a more singable, less zig-zaggy folk-tune shape
        start = carry_start(mel_choices, prev_mel_val)
        mel_contour = contour_sequence(12, choices=mel_choices, start=start, reversal_bias=0.4, max_run=3)
        for i,d in enumerate(mel_contour):
            step = s0 + i
            if step>=s0+bar_len: break
            notes.append(mk(step, scale_tone(key_pc,scale,deg+d,5), "8n", 0.5+random.uniform(0,0.15)))
        prev_mel_val = mel_contour[-1]
        # grace note ornament before the phrase resolves
        notes.append(mk(s0+14, scale_tone(key_pc,scale,deg+1,5), "32n", 0.4))
    return notes


# =================================================================
# STYLE 5 — CLASSICAL PERIOD (Alberti bass):
#   the Mozart/Haydn accompaniment pattern: broken triad (order picked
#   from a pool), quality derived from the scale, + a periodic
#   (antecedent/consequent) melodic phrase on top (picked from a pool)
# =================================================================
def gen_classical_alberti(key_pc, scale_name, bpm, steps):
    notes = []
    scale = "major"
    prog_pool = [
        [0,4,5,4],   # I-V-vi-V
        [0,3,4,0],   # I-IV-V-I
        [0,5,3,4],   # I-vi-IV-V
    ]
    prog = random.choice(prog_pool)
    n = len(prog)
    bar_len = BAR_STEPS
    num_bars = steps // bar_len

    alberti_order = random.choice([[0,2,1,2],[0,1,2,1]])

    # relative scale-degree offsets from each bar's chord root, spanning a
    # full octave — a real contour, continued bar-to-bar, instead of a
    # fixed antecedent/consequent pair shared by every generation
    mel_choices = (0,1,2,3,4,5,6,7)

    prev_mel_val = None
    for bar in range(num_bars):
        local_bar = bar % n
        deg = prog[local_bar]
        qual = diatonic_quality(scale, deg)
        s0 = bar*bar_len
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        triad = chord_tones(root_pc, qual, 3)
        # ALBERTI PATTERN: broken triad, repeated across the bar
        for i in range(8):
            step = s0+i*2
            note = triad[alberti_order[i%4]]
            notes.append(mk(step, note, "8n", 0.45))

        # periodic melody: antecedent (first half of the phrase) answered
        # by consequent (second half) — enforced by resolving the very
        # last note of each n-bar phrase to the tonic (chord root)
        start = carry_start(mel_choices, prev_mel_val)
        phrase = contour_sequence(4, choices=mel_choices, start=start, reversal_bias=0.45, max_run=3)
        if local_bar == n-1:
            phrase = phrase[:-1] + [0]
        for i,d in enumerate(phrase):
            notes.append(mk(s0+i*4, scale_tone(key_pc,scale,deg+d,5), "4n", 0.7-0.05*i))
        prev_mel_val = phrase[-1]
        if local_bar==n-1:  # classical cadential trill
            for k in range(4):
                notes.append(mk(s0+12+k, scale_tone(key_pc,scale, (2 if k%2==0 else 0),6), "32n", 0.55))
    return notes



# =================================================================
# STYLE 6 — RENAISSANCE, imitative polyphony:
#   4-voice texture (SATB registers): Soprano presents a short motif
#   at bar 0; Alto answers with the same motif 8 steps later (2 beats
#   = the simplest imitative entry interval). Tenor adds a stepwise
#   inner voice with optional 4−3 / 7−6 suspension at each bar
#   boundary. Bass provides root + fifth on alternate beats. Modal
#   progressions (Dorian, Phrygian, Mixolydian) — no functional V7→I.
#   Phrygian cadence (♭II→I) or Landini ornament (6–7–1 in Soprano)
#   on the final bar.
#
#   INVARIANT: steps must be a positive multiple of BAR_STEPS (16).
#   generate_loop() enforces this via ValueError before calling here.
# =================================================================
def gen_renaissance(key_pc, scale_name, bpm, steps, mode="dorian"):
    notes = []
    scale = mode

    PROGS = {
        "dorian": [
            [0, 6, 5, 6],   # i – ♭VII – vi° – ♭VII
            [0, 3, 4, 0],   # i – iv – v – i
            [0, 5, 3, 4],   # i – vi° – iv – v
        ],
        "phrygian": [
            [0, 1, 0, 4],   # i – ♭II – i – v°  (characteristic Phrygian colour)
            [0, 6, 1, 0],   # i – ♭vii – ♭II – i
        ],
        "mixolydian": [
            [0, 6, 3, 0],   # I – ♭VII – IV – I
            [0, 3, 6, 4],   # I – IV – ♭VII – v
        ],
    }
    prog   = random.choice(PROGS.get(scale, PROGS["dorian"]))
    n_prog = len(prog)
    num_bars = steps // BAR_STEPS

    R_SOP, R_ALT, R_TEN, R_BAS = 5, 4, 3, 2

    # ── IMITATIVE MOTIF ────────────────────────────────────────
    # Scale-degree offsets from chord root, durations chosen once per loop.
    # Total motif length ≤ BAR_STEPS so it fits cleanly within one bar.
    MOT_DUR_SETS = [
        [("4n", 4), ("4n", 4), ("8n", 2), ("8n", 2)],   # 12 steps
        [("2n", 8), ("4n", 4), ("8n", 2), ("8n", 2)],   # 16 steps
        [("4n", 4), ("8n", 2), ("8n", 2), ("4n", 4)],   # 12 steps
    ]
    mot_durs   = random.choice(MOT_DUR_SETS)
    mot_offsets = contour_sequence(len(mot_durs), choices=(0, 1, 2, 3, 4), max_run=2)
    motif_steps = sum(span for _, span in mot_durs)
    imitation_delay = 8                              # Alto enters 2 beats after Soprano
    alt_free_from   = imitation_delay + motif_steps  # step from which Alto plays freely

    def place_motif(start_step, root_deg, octave, vel_base):
        step = start_step
        for off, (dur, span) in zip(mot_offsets, mot_durs):
            if step >= steps:
                break
            notes.append(mk(step,
                            scale_tone(key_pc, scale, root_deg + off, octave),
                            dur,
                            round(vel_base + random.uniform(-0.04, 0.04), 2)))
            step += span

    sop_prev = None
    alt_prev = None
    ten_prev = None

    for bar in range(num_bars):
        deg     = prog[bar % n_prog]
        s0      = bar * BAR_STEPS
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        qual    = diatonic_quality(scale, deg)
        is_last = (bar == num_bars - 1)
        fifth_iv = CHORD_QUALITIES[qual][2]

        # ── BASS: root on beat 1, fifth on beat 3 ─────────────────
        # Skipped on the final bar — cadence block supplies its own bass.
        if not is_last:
            notes.append(mk(s0,   note_name(root_pc,             R_BAS), "4n", 0.60))
            notes.append(mk(s0+8, note_name(root_pc + fifth_iv,  R_BAS), "4n", 0.50))

        # ── TENOR: inner stepwise voice, optional suspension ────────
        ten_choices = (deg, deg+1, deg+2, deg+3, deg+4)
        ten_start   = carry_start(ten_choices, ten_prev)
        ten_contour = contour_sequence(2, choices=ten_choices, start=ten_start,
                                       reversal_bias=0.35, max_run=3)
        if ten_prev is not None and not is_last and random.random() < 0.30:
            # Suspension: hold the previous scale degree one beat into the
            # new bar (dissonant), then resolve down by one diatonic step.
            notes.append(mk(s0,   scale_tone(key_pc, scale, ten_prev,     R_TEN), "8n", 0.45))
            notes.append(mk(s0+2, scale_tone(key_pc, scale, ten_prev - 1, R_TEN), "8n", 0.40))
            notes.append(mk(s0+8, scale_tone(key_pc, scale, ten_contour[-1], R_TEN), "4n", 0.42))
        else:
            notes.append(mk(s0,   scale_tone(key_pc, scale, ten_contour[0], R_TEN), "2n", 0.45))
            notes.append(mk(s0+8, scale_tone(key_pc, scale, ten_contour[1], R_TEN), "4n", 0.42))
        ten_prev = ten_contour[-1]

        # ── SOPRANO: presents motif on bar 0, free counterpoint after ─
        if bar == 0:
            place_motif(s0, deg, R_SOP, 0.65)
            sop_prev = deg + mot_offsets[-1]
        elif not is_last:
            sop_choices = (deg, deg+2, deg+4, deg+6, deg+1)
            sop_contour = contour_sequence(2, choices=sop_choices,
                                           start=carry_start(sop_choices, sop_prev))
            notes.append(mk(s0+4,  scale_tone(key_pc, scale, sop_contour[0], R_SOP), "4n", 0.65))
            notes.append(mk(s0+12, scale_tone(key_pc, scale, sop_contour[1], R_SOP), "4n", 0.55))
            sop_prev = sop_contour[-1]

        # ── ALTO: imitation in bar 0; free after motif finishes ─────
        # Guard: don’t emit free-counterpoint notes for bars whose
        # start step is still inside the imitation window (alt_free_from).
        if bar == 0:
            place_motif(s0 + imitation_delay, deg, R_ALT, 0.55)
            alt_prev = deg + mot_offsets[-1]
        elif s0 >= alt_free_from and not is_last:
            alt_choices = (deg, deg+1, deg+2, deg+3, deg+4)
            alt_contour = contour_sequence(3, choices=alt_choices,
                                           start=carry_start(alt_choices, alt_prev),
                                           reversal_bias=0.40, max_run=2)
            notes.append(mk(s0,    scale_tone(key_pc, scale, alt_contour[0], R_ALT), "4n", 0.50))
            notes.append(mk(s0+6,  scale_tone(key_pc, scale, alt_contour[1], R_ALT), "4n", 0.47))
            notes.append(mk(s0+12, scale_tone(key_pc, scale, alt_contour[2], R_ALT), "4n", 0.45))
            alt_prev = alt_contour[-1]

        # ── CADENCE: multi-bar loops only ───────────────────────────────
        # Skipped on 1-bar loops: the Soprano motif already occupies bar 0
        # and the cadence block would emit additional bass + soprano notes at
        # the same steps (verified: step 8 gets 5 notes in a 1-bar loop).
        if is_last and num_bars > 1:
            final_pc = key_pc
            if mode == "phrygian":
                # Phrygian cadence: ♭II → I (bass descends by semitone)
                flat_ii_pc = key_pc + SCALES[scale][1]
                notes.append(mk(s0,   note_name(flat_ii_pc, R_BAS), "4n", 0.65))
                notes.append(mk(s0+8, note_name(final_pc,   R_BAS), "2n", 0.70))
                notes.append(mk(s0+4, scale_tone(key_pc, scale, 1, R_SOP), "4n", 0.65))
                notes.append(mk(s0+8, scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70))
            else:
                # Landini cadence: V in bass, 6–7–1 ornament in soprano
                v_pc = key_pc + SCALES[scale][4]
                notes.append(mk(s0,   note_name(v_pc,     R_BAS), "4n", 0.60))
                notes.append(mk(s0+8, note_name(final_pc, R_BAS), "2n", 0.65))
                for k, loff in enumerate([5, 6, 0]):
                    notes.append(mk(s0 + 8 + k * 2,
                                    scale_tone(key_pc, scale, loff, R_SOP),
                                    "8n", max(0.40, 0.68 - k * 0.05)))

    return notes


# ---------------------------------------------------------------
# MASTER DISPATCH
# ---------------------------------------------------------------
STYLE_META = {
    "neoclassical_major": dict(scale="major",          swing=0.0,  segment_steps=BAR_STEPS,             fn=lambda kp,s,b,st: gen_neoclassical(kp,s,b,st,minor=False)),
    "neoclassical_minor": dict(scale="harmonic_minor",  swing=0.0,  segment_steps=BAR_STEPS,             fn=lambda kp,s,b,st: gen_neoclassical(kp,s,b,st,minor=True)),
    "baroque_major":      dict(scale="major",          swing=0.0,  segment_steps=BAROQUE_SEGMENT_STEPS, fn=lambda kp,s,b,st: gen_baroque(kp,s,b,st,minor=False)),
    "baroque_minor":      dict(scale="harmonic_minor",  swing=0.0,  segment_steps=BAROQUE_SEGMENT_STEPS, fn=lambda kp,s,b,st: gen_baroque(kp,s,b,st,minor=True)),
    "jazz_major":         dict(scale="major",          swing=0.6,  segment_steps=BAR_STEPS,             fn=lambda kp,s,b,st: gen_jazz(kp,s,b,st,minor=False)),
    "jazz_minor":         dict(scale="dorian",         swing=0.6,  segment_steps=BAR_STEPS,             fn=lambda kp,s,b,st: gen_jazz(kp,s,b,st,minor=True)),
    "modal_folk":         dict(scale="dorian",         swing=0.15, segment_steps=BAR_STEPS,             fn=lambda kp,s,b,st: gen_modal_folk(kp,s,b,st)),
    "classical_alberti":  dict(scale="major",      swing=0.0,  segment_steps=BAR_STEPS, fn=lambda kp,s,b,st: gen_classical_alberti(kp,s,b,st)),
    "renaissance_dorian":     dict(scale="dorian",      swing=0.0,  segment_steps=BAR_STEPS, fn=lambda kp,s,b,st: gen_renaissance(kp,s,b,st,mode="dorian")),
    "renaissance_phrygian":   dict(scale="phrygian",    swing=0.0,  segment_steps=BAR_STEPS, fn=lambda kp,s,b,st: gen_renaissance(kp,s,b,st,mode="phrygian")),
    "renaissance_mixolydian": dict(scale="mixolydian",  swing=0.0,  segment_steps=BAR_STEPS, fn=lambda kp,s,b,st: gen_renaissance(kp,s,b,st,mode="mixolydian")),
}

def generate_loop(style, key, name=None, bpm=BPM_DEFAULT, steps=STEPS_DEFAULT, seed=None):
    if seed is not None:
        random.seed(seed)
    meta = STYLE_META[style]
    seg = meta["segment_steps"]
    if steps <= 0 or steps % seg != 0:
        raise ValueError(
            f"steps must be a positive multiple of {seg} for style '{style}' (got {steps})"
        )
    key_pc = PC[key]
    notes = meta["fn"](key_pc, meta["scale"], bpm, steps)
    notes.sort(key=lambda x: x["step"])
    _MINOR_MODES = {"natural_minor", "harmonic_minor", "melodic_minor_asc",
                    "dorian", "phrygian", "locrian"}
    scale_label = "Minor" if meta["scale"] in _MINOR_MODES else "Major"
    return {
        "name": name or f"{style.replace('_',' ').title()} in {key}",
        "bpm": bpm, "instrument": "piano", "steps": steps,
        "key": key, "scale": scale_label, "swing": meta["swing"], "notes": notes,
        "style": style,
    }

if __name__ == "__main__":
    KEYS_DEMO = ["C","G","D","A","F","E"]
    demo = []
    for i,style in enumerate(STYLE_META.keys()):
        for j in range(2):
            key = KEYS_DEMO[(i*2+j) % len(KEYS_DEMO)]
            demo.append(generate_loop(style, key, seed=500+i*2+j))
    print("generated:", len(demo))
    for l in demo:
        dur = l["steps"]*(60.0/l["bpm"]/4.0)
        assert dur >= 8.0
        assert all(0 <= n["step"] < l["steps"] for n in l["notes"]), "note stepped outside the loop"
        assert all(0 <= n["velocity"] <= 1 for n in l["notes"]), "velocity out of range"
        print(f"{l['name']:34s} style={l['style']:20s} notes:{len(l['notes']):3d} swing:{l['swing']}")

    short_loop = generate_loop("jazz_minor", "A", steps=32, seed=1)
    assert all(n["step"] < 32 for n in short_loop["notes"])
    long_loop = generate_loop("baroque_major", "D", steps=96, seed=1)
    assert all(n["step"] < 96 for n in long_loop["notes"])
    try:
        generate_loop("jazz_minor", "A", steps=20)
        raise AssertionError("expected ValueError for a steps value that isn't a valid multiple")
    except ValueError:
        pass
    print("steps-axis checks passed (32, 96, and invalid-20 all behaved correctly)")

    demo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theory_engine_demo.json")
    with open(demo_path, "w", encoding="utf-8") as f:
        json.dump(demo, f, ensure_ascii=False, indent=2)
    print(f"Demo written to: {demo_path}")
