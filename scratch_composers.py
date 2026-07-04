import random

def mk(step, note, dur, vel): return {"step": step, "note": note, "duration": dur, "velocity": round(vel,2)}

def note_name(semitone, octave):
    NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
    idx = semitone % 12
    octv = octave + semitone // 12
    return f"{NOTE_NAMES[idx]}{octv}"

CHORD_QUALITIES = {
    "maj":   [0,4,7],
    "min":   [0,3,7],
    "dim":   [0,3,6],
    "aug":   [0,4,8],
    "maj7":  [0,4,7,11],
    "min7":  [0,3,7,10],
    "dom7":  [0,4,7,10],
    "m7b5":  [0,3,6,10],
}

SCALES = {
    "major":              [0,2,4,5,7,9,11],
    "natural_minor":      [0,2,3,5,7,8,10],
    "harmonic_minor":     [0,2,3,5,7,8,11],
    "dorian":             [0,2,3,5,7,9,10],
}

def scale_tone(key_pc, scale_name, degree, octave):
    scale = SCALES[scale_name]
    n = len(scale)
    octv_add, d = divmod(degree, n)
    return note_name(key_pc + scale[d], octave + octv_add)

def carry_start(choices, prev_value):
    if prev_value is None: return None
    return min(range(len(choices)), key=lambda i: abs(choices[i]-prev_value))

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

def nearest_register(pc, center):
    k = round((center - pc) / 12)
    return pc + 12*k

def voice_lead(intervals, root_pc, prev_voicing, anchor_octave=4):
    pitch_classes = [(root_pc + iv) % 12 for iv in intervals]
    center = (sum(prev_voicing)/len(prev_voicing)) if prev_voicing else anchor_octave*12
    return sorted(nearest_register(pc, center) for pc in pitch_classes)

def realize(abs_pitches): return [note_name(p, 0) for p in abs_pitches]


def gen_einaudi(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "natural_minor"
    progs = [
        [(5, "maj"), (3, "min"), (0, "min"), (4, "min")], # VI - iv - i - v
        [(0, "min"), (5, "maj"), (2, "maj"), (6, "maj")], # i - VI - III - VII
    ]
    prog = random.choice(progs)
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps
    
    prev_mel = None
    
    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        
        chord_ivs = CHORD_QUALITIES[qual]
        arp_pitches = [
            root_pc - 12,
            root_pc - 12 + chord_ivs[1],
            root_pc - 12 + chord_ivs[2],
            root_pc,
            root_pc + chord_ivs[1],
            root_pc + chord_ivs[2]
        ]
        
        arp_len = beats_per_bar * 2 
        for b in range(arp_len):
            step = s0 + b * 2
            idx = b if b < len(arp_pitches) else len(arp_pitches) - 1 - (b - len(arp_pitches))
            if idx >= len(arp_pitches): idx = len(arp_pitches) - 1
            if idx < 0: idx = 0
            
            notes.append(mk(step, note_name(arp_pitches[idx], 3), "8n", 0.45 + 0.1 * (b % 2 == 0)))
            
        if bar % 2 == 0:
            mel_choices = (0, 1, 2, 4)
            start = carry_start(mel_choices, prev_mel)
            mel_contour = contour_sequence(1, choices=mel_choices, start=start)
            notes.append(mk(s0, scale_tone(key_pc, scale, deg + mel_contour[0], 5), "1n", 0.65))
            prev_mel = mel_contour[-1]

    return notes

def gen_glass(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "dorian"
    progs = [
        [(0, "min"), (0, "min"), (5, "maj"), (5, "maj")],
        [(0, "min"), (0, "min"), (3, "maj"), (3, "maj")],
    ]
    prog = random.choice(progs)
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps
    
    pattern_len = 3 
    
    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        
        chord_ivs = CHORD_QUALITIES[qual]
        pattern = [root_pc, root_pc + chord_ivs[1], root_pc + chord_ivs[2]]
        if random.random() < 0.5:
            pattern = [root_pc, root_pc + chord_ivs[2], root_pc + 12]
            
        for i in range(beats_per_bar * 2):
            global_eighth = bar * (beats_per_bar * 2) + i
            p_idx = global_eighth % pattern_len
            step = s0 + i * 2
            vel = 0.6 if p_idx == 0 else 0.4
            notes.append(mk(step, note_name(pattern[p_idx], 4), "8n", vel))
            
            if bar % 2 == 0 and i == 0:
                notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.5))

    return notes

def gen_tiersen(key_pc, scale_name, bpm, steps, beats_per_bar=3):
    notes = []
    scale = "harmonic_minor"
    progs = [
        [(0, "min"), (4, "dom7"), (0, "min"), (4, "dom7")],
        [(0, "min"), (5, "maj"), (3, "min"), (4, "dom7")],
    ]
    prog = random.choice(progs)
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps
    
    prev_mel = None
    
    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        
        notes.append(mk(s0, note_name(root_pc, 2), "4n", 0.65)) 
        
        chord_ivs = CHORD_QUALITIES[qual]
        chord_notes = [note_name(root_pc + iv, 3) for iv in chord_ivs]
        for b in range(1, beats_per_bar):
            for cn in chord_notes:
                notes.append(mk(s0 + b * 4, cn, "4n", 0.45))
                
        mel_choices = (0, 1, 2, 3, 4, 5)
        start = carry_start(mel_choices, prev_mel)
        mel_contour = contour_sequence(bar_steps, choices=mel_choices, start=start, reversal_bias=0.2, max_run=4)
        
        for i, ci in enumerate(mel_contour):
            step = s0 + i
            notes.append(mk(step, scale_tone(key_pc, scale, deg + ci, 5), "16n", 0.5 + random.uniform(0, 0.15)))
            
        prev_mel = mel_contour[-1]

    return notes

def gen_frahm(key_pc, scale_name, bpm, steps, beats_per_bar=4):
    notes = []
    scale = "natural_minor" if random.random() < 0.7 else "major"
    progs = [
        [(0, "min"), (0, "min"), (3, "min"), (3, "min")], 
        [(0, "min"), (0, "min"), (5, "maj"), (5, "maj")],
        [(0, "maj"), (0, "maj"), (3, "maj"), (3, "maj")],
    ]
    prog = random.choice(progs)
    if scale == "major": prog = progs[2]
    else: prog = random.choice(progs[:2])
    
    n = len(prog)
    bar_steps = beats_per_bar * 4
    num_bars = steps // bar_steps
    
    prev_pad = None
    pulse_note = note_name(key_pc, 4)
    if scale == "natural_minor":
        pulse_note = note_name(key_pc + 7, 4)
        
    for bar in range(num_bars):
        deg, qual = prog[bar % n]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        
        if bar % 2 == 0:
            pad_pitches = voice_lead(CHORD_QUALITIES[qual], root_pc, prev_pad, anchor_octave=3)
            for note in realize(pad_pitches):
                notes.append(mk(s0, note, "1n", 0.25)) 
            notes.append(mk(s0, note_name(root_pc, 2), "1n", 0.3))
            prev_pad = pad_pitches
            
        for i in range(beats_per_bar * 2):
            step = s0 + i * 2
            notes.append(mk(step, pulse_note, "8n", 0.3 + 0.05 * (i % 2 == 0)))
            
    return notes

if __name__ == "__main__":
    print(gen_einaudi(0, "natural_minor", 100, 64, 4))
    print(gen_glass(0, "dorian", 100, 64, 4))
    print(gen_tiersen(0, "harmonic_minor", 100, 48, 3))
    print(gen_frahm(0, "major", 100, 64, 4))
