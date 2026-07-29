import random
import math

NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
PC = {n:i for i,n in enumerate(NOTE_NAMES)}

def note_name(semitone, octave):
    idx = semitone % 12
    octv = octave + semitone // 12
    return f"{NOTE_NAMES[idx]}{octv}"

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
    # extra modes/colors for more variety
    "lydian_dominant":    [0,2,4,6,7,9,10],
    "phrygian_dominant":  [0,1,4,5,7,8,10],
    "whole_tone":         [0,2,4,6,8,10],
    "harmonic_major":     [0,2,4,5,7,8,11],
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

SEVENTH_QUALITY_MAP = {
    (4,7,11): "maj7",
    (3,7,10): "min7",
    (4,7,10): "dom7",
    (3,6,10): "m7b5",
    (3,6,9):  "dim7",
    (4,8,10): "aug7",
    # (4,7,11)+(0,): "maj7",  <- removed garbage entry as requested
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
        return random.choice(["dom9", "dom13", "dom7b9", "dom7#9", "dom7alt"])
    return quality

CHORD_QUALITIES = {
    "maj":     [0,4,7],
    "min":     [0,3,7],
    "dim":     [0,3,6],
    "aug":     [0,4,8],
    "sus2":    [0,2,7],
    "sus4":    [0,5,7],
    "maj6":    [0,4,7,9],
    "min6":    [0,3,7,9],
    "add9":    [0,4,7,14],
    "min_add9":[0,3,7,14],
    "maj7":    [0,4,7,11],
    "min7":    [0,3,7,10],
    "dom7":    [0,4,7,10],
    "m7b5":    [0,3,6,10],
    "dim7":    [0,3,6,9],
    "aug7":    [0,4,8,10],
    "dom9":    [0,4,7,10,14],
    "min9":    [0,3,7,10,14],
    "maj9":    [0,4,7,11,14],
    "dom13":   [0,4,7,10,14,21],
    "dom7b9":  [0,4,7,10,13],
    "dom7#9":  [0,4,7,10,15],
    "dom7alt": [0,4,8,10,13],  # altered dominant flavor
    "min11":   [0,3,7,10,14,17],
}

def chord_tones(root_pc, quality, octave):
    unique_ivs = sorted(set(iv % 12 for iv in CHORD_QUALITIES[quality]))
    return [note_name(root_pc+iv, octave) for iv in unique_ivs]

def shell_intervals(quality):
    ivs = CHORD_QUALITIES[quality]
    return [ivs[0], ivs[1], ivs[3]] if len(ivs) >= 4 else list(ivs)

# ---------------------------------------------------------------------------
# HARMONY GENERATION — weighted, non-deterministic, with borrowed/secondary chords
# ---------------------------------------------------------------------------

# weights instead of flat lists: (degree -> {target_degree: weight})
MAJOR_TRANSITIONS = {
    0: {0:2, 1:8, 2:6, 3:12, 4:14, 5:10, 6:6},
    1: {4:10, 6:5, 3:3, 2:2},
    2: {5:8, 3:6, 4:3, 1:2},
    3: {4:12, 0:8, 1:6, 5:6, 2:2},
    4: {0:12, 5:6, 3:3, 6:2},
    5: {3:8, 1:7, 4:6, 2:3, 0:2},
    6: {0:8, 2:4, 4:2},
}
MINOR_TRANSITIONS = {
    0: {0:2, 1:6, 2:8, 3:12, 4:12, 5:10, 6:6},
    1: {4:10, 6:5, 3:3},
    2: {5:8, 3:6, 6:4, 0:2},
    3: {4:12, 0:8, 1:6, 5:6},
    4: {0:12, 5:6, 3:3},
    5: {3:8, 1:6, 4:6, 2:4},
    6: {2:6, 0:8},
}

def _weighted_choice(weight_map):
    keys = list(weight_map.keys())
    weights = list(weight_map.values())
    return random.choices(keys, weights=weights, k=1)[0]

def generate_harmony(scale_type, length=4, start_degree=None,
                      secondary_dominant_prob=0.18,
                      borrowed_chord_prob=0.15,
                      chromatic_passing_prob=0.10,
                      detailed=False):
    """
    Returns a list of dicts: {"degree": int, "quality": str|None, "borrowed": bool,
                               "secondary_of": int|None, "chromatic": bool}
    quality=None means "use diatonic quality as normal".
    """
    is_minor = "minor" in scale_type or scale_type in ["dorian", "phrygian", "aeolian", "locrian"]
    transitions = MINOR_TRANSITIONS if is_minor else MAJOR_TRANSITIONS

    if start_degree is not None:
        current = start_degree
    else:
        current = random.choices([0,5,3,1,2,4], weights=[40,18,14,10,10,8], k=1)[0]

    prog = []
    for i in range(length):
        entry = {"degree": current, "quality": None, "borrowed": False,
                 "secondary_of": None, "chromatic": False}

        # occasionally insert a secondary dominant resolving INTO the next chord
        if i < length - 1 and random.random() < secondary_dominant_prob:
            options = transitions.get(current, {0:1})
            nxt = _weighted_choice(options)
            entry2 = {"degree": (nxt + 4) % 7, "quality": "dom7",
                      "borrowed": False, "secondary_of": nxt, "chromatic": False}
            prog.append(entry)
            prog.append(entry2)
            current = nxt
            if len(prog) >= length:
                break
            continue

        # occasionally borrow a chord from the parallel mode (modal interchange)
        if random.random() < borrowed_chord_prob:
            entry["borrowed"] = True
            entry["quality"] = random.choice(["min", "maj", "dim", "min7", "maj7"])

        # occasionally insert a chromatic passing chord before moving on
        if random.random() < chromatic_passing_prob and i < length - 1:
            entry["chromatic"] = True

        prog.append(entry)
        if len(prog) >= length:
            break
        options = transitions.get(current, {0:1})
        current = _weighted_choice(options)

    # BACKWARDS COMPATIBILITY FIX:
    # All other generator modules (jazz, minimalism, baroque, etc.) currently expect
    # a list of integers (the scale degrees). If `detailed=True` is not explicitly
    # passed, we return just the degrees to prevent type errors across the codebase.
    if not detailed:
        return [d["degree"] for d in prog[:length]]
    
    return prog[:length]

def nearest_register(pc, center):
    k = round((center - pc) / 12)
    return pc + 12*k

def voice_lead(intervals, root_pc, prev_voicing, anchor_octave=4, min_gap=3, max_octave=5,
                jump_prob=0.12):
    """Mostly smooth voice leading, but with occasional deliberate register jumps
    for variety (avoids everything sounding glued to the same range)."""
    pitch_classes = [(root_pc + iv) % 12 for iv in intervals]
    center = (sum(prev_voicing)/len(prev_voicing)) if prev_voicing else anchor_octave*12

    if prev_voicing and random.random() < jump_prob:
        center += random.choice([-12, 12])

    first = nearest_register(pitch_classes[0], center)
    if first > max_octave * 12:
        first -= 12
    if first < (max_octave - 3) * 12:
        first += 12

    pitches = [first]
    for pc in pitch_classes[1:]:
        prev = pitches[-1]
        k = -(-(prev + min_gap - pc) // 12)
        pitches.append(pc + 12*k)

    # small chance to drop or add an octave doubling for texture
    if random.random() < 0.15:
        pitches.append(pitches[0] + 12)

    return pitches

def realize(abs_pitches):
    return [note_name(p, 0) for p in abs_pitches]

def maybe_add_color(intervals, prob=0.35):
    """Wider palette of possible color tones (9, 11, 13, b9, #11) instead of just 14."""
    color_pool = [14, 17, 21, 13, 18]
    ivs = list(intervals)
    if random.random() < prob:
        c = random.choice(color_pool)
        if c not in ivs:
            ivs.append(c)
    return ivs

def carry_start(choices, prev_value):
    if prev_value is None:
        return None
    return min(range(len(choices)), key=lambda i: abs(choices[i]-prev_value))

BPM_DEFAULT = 100
STEPS_DEFAULT = 64
SPAN_TO_DURATION = {1:"16n", 2:"8n", 3:"8t", 4:"4n", 6:"4n.", 8:"2n", 16:"1n"}

def mk(step, note, dur, vel, steps_total, humanize=True):
    s = int(round(step)) % steps_total
    v = max(0.0, min(1.0, vel))
    if humanize:
        # tiny velocity/timing humanization so grids don't sound robotic
        v = max(0.0, min(1.0, v + random.uniform(-0.05, 0.05)))
    return {"step": s, "note": note, "duration": dur, "velocity": round(v, 2)}

def contour_sequence(n, choices=(0,1,2,3), start=None, reversal_bias=0.55, max_run=2,
                      leap_prob=0.15):
    """Adds occasional leaps (jumping 2+ steps in the choice list) instead of
    only ever moving by a single step, so melodic contour varies more."""
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
        step_size = random.choice([2, 3]) if random.random() < leap_prob else 1
        idx = (idx + direction * step_size) % len(choices)
    return seq

def choose_scale(weighted=True):
    """Helper to pick a scale with sensible weighting so exotic modes show up
    sometimes but don't dominate."""
    common = ["major","natural_minor","dorian","mixolydian","minor_pentatonic"]
    rare = ["phrygian","lydian","locrian","harmonic_minor","melodic_minor_asc",
            "blues","major_pentatonic","lydian_dominant","phrygian_dominant",
            "whole_tone","harmonic_major"]
    if not weighted:
        return random.choice(common + rare)
    return random.choice(common) if random.random() < 0.65 else random.choice(rare)
