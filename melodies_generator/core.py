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

def nearest_register(pc, center):
    k = round((center - pc) / 12)
    return pc + 12*k

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

BPM_DEFAULT = 100

STEPS_DEFAULT = 64

SPAN_TO_DURATION = {1:"16n", 2:"8n", 3:"8t", 4:"4n", 6:"4n.", 8:"2n", 16:"1n"}

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

