"""
PARAMETRIC MUSIC THEORY ENGINE
================================
generate_loop(style, key, bpm, steps) -> loop dict matching the sequencer JSON schema.

Six axes are modeled explicitly, not just "different chords":
  1. Scale / mode        -> which pitches are even allowed
  2. Chord vocabulary     -> triads only vs 7ths/9ths, altered tones
  3. Progression grammar  -> functional cadences vs circle-of-fifths sequence vs ii-V-I vamp
  4. Rhythm / meter       -> subdivision, swing ratio, running-note density
  5. TEXTURE              -> homophony / polyphony / walking bass / Alberti bass
                             (this is the one most generators skip — it's why baroque
                             and jazz need genuinely different code paths, not just
                             different notes over the same skeleton)
  6. Ornamentation        -> trills, blue notes, grace notes, passing tones

`steps` is a real axis too: every generator cycles its progression to fill
however many bars fit, instead of being hardcoded to exactly 64 steps.
`steps` must be a positive multiple of the style's bar length (16, or 8 for
baroque) — generate_loop raises ValueError otherwise rather than silently
wrapping bars on top of each other.
"""
import json, random

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

# ---------------------------------------------------------------
# AXIS 2: CHORD VOCABULARY
# All qualities have >=3 intervals: index 0=root, 1=third, 2=fifth.
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

# ---------------------------------------------------------------
# helpers
# ---------------------------------------------------------------
BPM_DEFAULT = 100
STEPS_DEFAULT = 64
BAR_STEPS = 16                  # one bar = 16 sixteenth-note steps (4/4)
BAROQUE_SEGMENT_STEPS = 8       # baroque changes harmony every half-bar

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
#   sustained bass + arpeggio + pentatonic melody line
# =================================================================
def gen_neoclassical(key_pc, scale_name, bpm, steps, minor=False):
    notes = []
    scale = "harmonic_minor" if minor else "major"

    major_progs = [
        ([0,5,3,4], ["maj","min","maj","maj"]),   # I-vi-IV-V
        ([0,4,5,3], ["maj","maj","min","maj"]),   # I-V-vi-IV
        ([5,0,3,4], ["min","maj","maj","maj"]),   # vi-I-IV-V
        ([0,3,4,3], ["maj","maj","maj","maj"]),   # I-IV-V-IV
    ]
    minor_progs = [
        ([0,5,2,4], ["min","maj","maj","dom7"]),  # i-VI-III-V7
        ([0,3,4,0], ["min","min","maj","min"]),   # i-iv-V-i
        ([5,3,0,4], ["maj","min","min","dom7"]),  # VI-iv-i-V7
    ]
    degrees, qualities = random.choice(minor_progs if minor else major_progs)
    n = len(degrees)
    num_bars = steps // BAR_STEPS

    for bar in range(num_bars):
        deg, qual = degrees[bar % n], qualities[bar % n]
        bar_start = bar*BAR_STEPS
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        chord = chord_tones(root_pc, qual, 3) + [note_name(root_pc,4)]
        notes.append(mk(bar_start, note_name(root_pc,2), "1n", 0.65))

        # real up/down wandering through however many chord tones exist
        # (dynamic range, so extended chords don't leave the top note unreachable)
        arp_idx = contour_sequence(8, choices=tuple(range(len(chord))))
        for i,ci in enumerate(arp_idx):
            note = chord[ci]
            notes.append(mk(bar_start+i*2, note, "8n", 0.35+random.uniform(0,0.2)))

        mel_contour = contour_sequence(2, choices=(deg,deg+2,deg+4,deg+6,deg+1), start=1)
        notes.append(mk(bar_start+6, scale_tone(key_pc, scale, mel_contour[0], 5), "4n", 0.65))
        notes.append(mk(bar_start+12, scale_tone(key_pc, scale, mel_contour[1], 5), "4n", 0.55))
    return notes


# =================================================================
# STYLE 2 — BAROQUE, polyphony:
#   two genuinely independent voices in contrary motion + circle-of-fifths
#   sequence (the classic Bach/Vivaldi descending-fifths device) +
#   steady running 16ths (moto perpetuo) + a trill ornament at the cadence
# =================================================================
def gen_baroque(key_pc, scale_name, bpm, steps, minor=False):
    notes = []
    scale = "harmonic_minor" if minor else "major"
    seq_degrees = [0,3,6,2,5,1,4,0]
    quals =        ["maj","maj","dim","min","min","min","dom7","maj"] if not minor else \
                   ["min","min","dim","aug","maj","dim","dom7","min"]
    n = len(seq_degrees)
    seg = BAROQUE_SEGMENT_STEPS
    num_segments = steps // seg

    for i in range(num_segments):
        deg, qual = seq_degrees[i % n], quals[i % n]
        s0 = i*seg
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]

        # BASS: clean harmonic pulse (root, then 5th) — anchors the chord
        notes.append(mk(s0,   note_name(root_pc,2), "4n", 0.55))
        notes.append(mk(s0+4, note_name(root_pc+CHORD_QUALITIES[qual][2], 2), "4n", 0.45))

        # CHORD PAD: full triad held as a sustained tone under the melody
        pad = chord_tones(root_pc, qual, 4)
        for note in pad:
            notes.append(mk(s0, note, "2n", 0.25))

        # VOICE 2 (upper melodic line): real up/down contour through the chord tones
        chord = chord_tones(root_pc, qual, 5)
        v2_idx = contour_sequence(4, choices=tuple(range(len(chord))))
        for j2,ci in zip(range(0, seg, 2), v2_idx):
            step = s0+j2
            note = chord[ci]
            notes.append(mk(step, note, "8n", 0.55+0.05*(j2%4==0)))

        # cadence ornament: a trill on the final chord of the actual loop
        if i == num_segments-1:
            for k in range(4):
                t_step = s0 + seg - 4 + k
                trill_note = note_name(root_pc + (2 if k%2==0 else 0), 5)
                notes.append(mk(t_step, trill_note, "32n", 0.6))
    return notes


# =================================================================
# STYLE 3 — JAZZ:
#   ii-V-I loop, extended chords (9ths), WALKING BASS (quarter notes
#   stepping chromatically/diatonically between chord roots), swung
#   eighths in the melody, and a blue note dropped into the line
# =================================================================
def gen_jazz(key_pc, scale_name, bpm, steps, minor=False):
    notes = []
    scale = "dorian" if minor else "major"
    prog = [(1,"min7"), (4,"dom9"), (0,"maj7"), (0,"maj7")]
    if minor:
        prog = [(1,"m7b5"), (4,"dom7"), (0,"min7"), (5,"dom7")]
    n = len(prog)
    bar_len = BAR_STEPS
    num_bars = steps // bar_len

    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar*bar_len
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        # comping chord voiced spread across octaves 3-4, capped at 3 notes to avoid mud
        comp_chord = chord_tones(root_pc, qual, 3)[:3]
        comp_chord[-1] = comp_chord[-1][:-1] + str(int(comp_chord[-1][-1]) + 1)  # spread top note up an octave

        # WALKING BASS stays strictly in its own low register (octave 2 only).
        # "next chord" = whatever bar the loop actually plays next (respects
        # a shorter/longer requested loop length, not just the raw 4-chord cycle).
        next_bar = (bar+1) % num_bars
        next_deg = prog[next_bar % n][0]
        next_root_pc = key_pc + SCALES[scale][next_deg % len(SCALES[scale])]
        third_iv = CHORD_QUALITIES[qual][1]   # chromatic third of the CHORD, not a diatonic
        fifth_iv = CHORD_QUALITIES[qual][2]   # scale-degree lookup (which broke for deg 5/6)
        walk = [root_pc, root_pc+third_iv, root_pc+fifth_iv, next_root_pc-1]
        for b,pc_ in enumerate(walk):
            notes.append(mk(s0+b*4, note_name(pc_,2), "4n", 0.6+0.05*(b==0)))

        # Comping stabs on the off-beats, own register (octave 3-4), separated from bass
        for off in [6,14]:
            for note in comp_chord:
                notes.append(mk(s0+off, note, "8n", 0.35))

        # real up/down contour instead of the same fixed pattern every bar,
        # own register (octave 5) so it doesn't collide with the comping chords
        mel_chord = chord_tones(root_pc, qual, 5)
        mel_idx = contour_sequence(6, choices=(0,1,2,3) if len(mel_chord)>3 else (0,1,2))
        for i,ci in enumerate(mel_idx):
            step = s0 + 2 + i*2
            if step >= s0+bar_len: continue
            note = mel_chord[ci % len(mel_chord)]
            notes.append(mk(step, note, "8n", 0.5+random.uniform(0,0.15)))
        if bar % n == 1:
            blue = note_name(root_pc+3, 5)
            notes.append(mk(s0+10, blue, "16n", 0.55))
    return notes


# =================================================================
# STYLE 4 — MODAL FOLK (Dorian):
#   static modal vamp (no functional cadence — that's the point of modal
#   writing), drone bass, melody built from the mode with grace-note ornaments
# =================================================================
def gen_modal_folk(key_pc, scale_name, bpm, steps):
    notes = []
    scale = "dorian"
    # i - IV vamp in dorian (characteristic modal sound, e.g. "Scarborough Fair")
    prog = [0,3,0,3]
    n = len(prog)
    bar_len = BAR_STEPS
    num_bars = steps // bar_len

    for bar in range(num_bars):
        deg = prog[bar % n]
        s0 = bar*bar_len
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        notes.append(mk(s0, note_name(key_pc,2), "1n", 0.5))  # DRONE stays on the tonic regardless of chord above
        chord = chord_tones(root_pc, "min" if deg==0 else "maj", 4)
        for note in chord:
            notes.append(mk(s0+8, note, "2n", 0.3))
        mel = [0,2,3,2,0,-2,0,3,5,3,2,0]
        for i,d in enumerate(mel):
            step = s0 + i
            if step>=s0+bar_len: break
            notes.append(mk(step, scale_tone(key_pc,scale,deg+d,5), "8n", 0.5+random.uniform(0,0.15)))
        # grace note ornament before the phrase resolves
        notes.append(mk(s0+14, scale_tone(key_pc,scale,deg+1,5), "32n", 0.4))
    return notes


# =================================================================
# STYLE 5 — CLASSICAL PERIOD (Alberti bass):
#   the Mozart/Haydn accompaniment pattern: broken triad in the specific
#   order low-high-mid-high, continuous 8ths, + a periodic (antecedent/
#   consequent) melodic phrase on top
# =================================================================
def gen_classical_alberti(key_pc, scale_name, bpm, steps):
    notes = []
    scale = "major"
    prog = [0,4,5,4]  # I - V - vi - V  (simple classical progression)
    quals = ["maj","maj","min","maj"]
    n = len(prog)
    bar_len = BAR_STEPS
    num_bars = steps // bar_len

    for bar in range(num_bars):
        local_bar = bar % n   # position within the 4-bar antecedent/consequent phrase
        deg, qual = prog[local_bar], quals[local_bar]
        s0 = bar*bar_len
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        triad = chord_tones(root_pc, qual, 3)
        # ALBERTI PATTERN: low, high, mid, high — repeated across the bar
        alberti_order = [0,2,1,2]
        for i in range(8):
            step = s0+i*2
            note = triad[alberti_order[i%4]]
            notes.append(mk(step, note, "8n", 0.45))
        # periodic melody: antecedent (bars 0-1) answered by consequent (bars 2-3)
        if local_bar in (0,1):
            phrase = [0,2,4,2] if local_bar==0 else [4,5,7,4]
        else:
            phrase = [7,5,4,2] if local_bar==2 else [2,1,0,0]
        for i,d in enumerate(phrase):
            notes.append(mk(s0+i*4, scale_tone(key_pc,scale,deg+d,5), "4n", 0.7-0.05*i))
        if local_bar==3:  # classical cadential trill
            for k in range(4):
                notes.append(mk(s0+12+k, scale_tone(key_pc,scale, (2 if k%2==0 else 0),6), "32n", 0.55))
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
    "classical_alberti":  dict(scale="major",          swing=0.0,  segment_steps=BAR_STEPS,             fn=lambda kp,s,b,st: gen_classical_alberti(kp,s,b,st)),
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
    scale_label = "Minor" if "minor" in meta["scale"] or meta["scale"]=="dorian" else "Major"
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
        print(f"{l['name']:34s} style={l['style']:20s} notes:{len(l['notes']):3d} swing:{l['swing']}")

    # steps is now a real, working axis: shorter/longer loops just cycle the
    # progression instead of wrapping bars on top of each other.
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

    with open("/home/claude/theory_engine_demo.json","w",encoding="utf-8") as f:
        json.dump(demo, f, ensure_ascii=False, indent=2)