import random
import math
from .core import *
def _ren_progression(mode, num_bars):
    # Authentic modal progressions instead of generic tonal Markov chain
    progs = []
    if mode == "dorian":
        progs = [
            [0, 6, 0, 4], # i - VII - i - v
            [0, 2, 3, 4], # i - III - IV - v
            [0, 6, 2, 4], # i - VII - III - v
            [0, 3, 4, 0], # i - IV - v - i
        ]
    elif mode == "phrygian":
        progs = [
            [0, 1, 0, 3], # i - II - i - iv
            [0, 3, 2, 1], # i - iv - III - II (descending to phrygian cadence)
            [0, 5, 1, 0], # i - VI - II - i
            [0, 1, 3, 1], # i - II - iv - II
        ]
    elif mode == "mixolydian":
        progs = [
            [0, 6, 0, 3], # I - VII - I - IV
            [0, 3, 4, 0], # I - IV - v - I
            [0, 1, 0, 6], # I - ii - I - VII
            [0, 4, 3, 0], # I - v - IV - I
        ]
    else:
        progs = [[0, 3, 4, 0]]
    
    # 20% chance of fauxbourdon (parallel 1st inversion, represented here as descending degrees)
    if random.random() < 0.20:
        return [0, 6, 5, 4][:num_bars] if num_bars < 4 else [0, 6, 5, 4] * (num_bars // 4 + 1)
        
    base_prog = random.choice(progs)
    prog = []
    for i in range(num_bars):
        prog.append(base_prog[i % len(base_prog)])
    return prog

def _ren_texture_dance(key_pc, scale, prog, bpm, steps, bar_steps):
    # Homophonic block chords (Pavane/Frottola)
    notes = []
    num_bars = steps // bar_steps
    rhythms = [
        [("2n", 8), ("4n", 4), ("4n", 4)],
        [("4n", 4), ("4n", 4), ("2n", 8)],
        [("4n.", 6), ("8n", 2), ("4n", 4), ("4n", 4)],
        [("4n", 4), ("8n", 2), ("8n", 2), ("4n", 4), ("4n", 4)],
    ]
    for bar in range(num_bars):
        deg = prog[bar]
        s0 = bar * bar_steps
        root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
        qual = diatonic_quality(scale, deg)
        chord_ints = CHORD_QUALITIES[qual]
        
        valid_rhythms = [r for r in rhythms if sum(span for _, span in r) == bar_steps]
        bar_rhythm = random.choice(valid_rhythms) if valid_rhythms else [[("4n", 4)] * (bar_steps // 4)]
        
        step = s0
        for dur, span in bar_rhythm:
            if step >= steps: break
            notes.append(mk(step, note_name(root_pc, 2), dur, 0.65, steps))
            notes.append(mk(step, note_name(root_pc + random.choice([chord_ints[1], chord_ints[2]]), 3), dur, 0.55, steps))
            notes.append(mk(step, note_name(root_pc + random.choice([chord_ints[1], chord_ints[2]]), 4), dur, 0.55, steps))
            notes.append(mk(step, note_name(root_pc + random.choice([0, chord_ints[1], chord_ints[2]]), 5), dur, 0.65, steps))
            step += span
    return notes

def _ren_texture_motet(key_pc, scale, prog, bpm, steps, bar_steps):
    # Strict imitation (Motet style)
    notes = []
    num_bars = steps // bar_steps
    mot_rhythm = [("4n", 4), ("4n", 4), ("8n", 2), ("8n", 2), ("2n", 8)]
    mot_offsets = contour_sequence(len(mot_rhythm), choices=(0,1,2,3,4,-1,-2), max_run=2)
    
    voices = [
        {"name": "Soprano", "reg": 5, "delay_bars": 0},
        {"name": "Alto",    "reg": 4, "delay_bars": 1},
        {"name": "Tenor",   "reg": 3, "delay_bars": 2},
        {"name": "Bass",    "reg": 2, "delay_bars": 3},
    ]
    if random.random() < 0.5:
        voices = [
            {"name": "Tenor",   "reg": 3, "delay_bars": 0},
            {"name": "Soprano", "reg": 5, "delay_bars": 1},
            {"name": "Bass",    "reg": 2, "delay_bars": 2},
            {"name": "Alto",    "reg": 4, "delay_bars": 3},
        ]
        
    for v in voices:
        prev_deg = None
        for bar in range(num_bars):
            if bar < v["delay_bars"]: continue
            deg = prog[bar]
            s0 = bar * bar_steps
            if bar == v["delay_bars"]:
                step = s0
                for (dur, span), off in zip(mot_rhythm, mot_offsets):
                    if step >= steps: break
                    notes.append(mk(step, scale_tone(key_pc, scale, deg + off, v["reg"]), dur, 0.6, steps))
                    step += span
                prev_deg = deg + mot_offsets[-1]
            else:
                choices = (deg, deg+1, deg-1, deg+2, deg-2)
                contour = contour_sequence(3, choices=choices, start=carry_start(choices, prev_deg))
                step = s0
                notes.append(mk(step, scale_tone(key_pc, scale, contour[0], v["reg"]), "2n", 0.55, steps))
                if bar_steps > 4:
                    notes.append(mk(step + min(8, bar_steps//2), scale_tone(key_pc, scale, contour[1], v["reg"]), "4n", 0.5, steps))
                prev_deg = contour[-1]
    return notes

def _ren_texture_counterpoint(key_pc, scale, prog, bpm, steps, bar_steps):
    # Flowing counterpoint with passing tones & suspensions
    notes = []
    num_bars = steps // bar_steps
    sop_prev, alt_prev, ten_prev, bas_prev = None, None, None, None
    
    for bar in range(num_bars):
        deg = prog[bar]
        s0 = bar * bar_steps
        
        bas_choices = (deg, deg+1, deg-1)
        bas_idx = carry_start(bas_choices, bas_prev)
        bas_val = bas_choices[bas_idx if bas_idx is not None else 0]
        if random.random() < 0.3 and bar_steps >= 8:
            notes.append(mk(s0, scale_tone(key_pc, scale, bas_val, 2), "4n", 0.6, steps))
            notes.append(mk(s0 + 4, scale_tone(key_pc, scale, bas_val-1, 2), "4n", 0.5, steps))
            notes.append(mk(s0 + 8, scale_tone(key_pc, scale, bas_val, 2), "2n", 0.6, steps))
            bas_prev = bas_val
        else:
            notes.append(mk(s0, scale_tone(key_pc, scale, bas_val, 2), "1n" if bar_steps==16 else "2n", 0.6, steps))
            bas_prev = bas_val
            
        ten_choices = (deg+2, deg+4, deg)
        ten_idx = carry_start(ten_choices, ten_prev)
        ten_val = ten_choices[ten_idx if ten_idx is not None else 0]
        notes.append(mk(s0, scale_tone(key_pc, scale, ten_val, 3), "4n.", 0.55, steps))
        notes.append(mk(s0 + 6, scale_tone(key_pc, scale, ten_val-1, 3), "8n", 0.5, steps))
        if bar_steps >= 8:
            notes.append(mk(s0 + 8, scale_tone(key_pc, scale, ten_val, 3), "2n", 0.55, steps))
        ten_prev = ten_val
        
        alt_choices = (deg+4, deg+2, deg+6)
        alt_idx = carry_start(alt_choices, alt_prev)
        alt_val = alt_choices[alt_idx if alt_idx is not None else 0]
        notes.append(mk(s0, scale_tone(key_pc, scale, alt_val, 4), "2n", 0.5, steps))
        if bar_steps >= 8:
            notes.append(mk(s0 + 8, scale_tone(key_pc, scale, alt_val-1, 4), "2n", 0.5, steps))
        alt_prev = alt_val-1
        
        sop_choices = (deg, deg+2, deg+4, deg+7)
        sop_idx = carry_start(sop_choices, sop_prev)
        sop_val = sop_choices[sop_idx if sop_idx is not None else 0]
        if bar > 0 and random.random() < 0.5: 
            notes.append(mk(s0, scale_tone(key_pc, scale, sop_prev, 5), "4n", 0.65, steps)) 
            notes.append(mk(s0 + 4, scale_tone(key_pc, scale, sop_val, 5), "4n", 0.6, steps))
            if bar_steps >= 8:
                notes.append(mk(s0 + 8, scale_tone(key_pc, scale, sop_val+1, 5), "2n", 0.6, steps))
            sop_prev = sop_val+1
        else:
            notes.append(mk(s0, scale_tone(key_pc, scale, sop_val, 5), "4n", 0.6, steps))
            notes.append(mk(s0 + 4, scale_tone(key_pc, scale, sop_val+1, 5), "4n", 0.6, steps))
            if bar_steps >= 8:
                notes.append(mk(s0 + 8, scale_tone(key_pc, scale, sop_val-1, 5), "2n", 0.6, steps))
            sop_prev = sop_val-1
    return notes

def gen_renaissance(key_pc, scale_name, bpm, steps, beats_per_bar=4, mode="dorian"):
    scale = mode
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)
    
    prog = _ren_progression(mode, num_bars)
    textures = [_ren_texture_dance, _ren_texture_motet, _ren_texture_counterpoint]
    chosen_texture = random.choice(textures)
    
    notes = chosen_texture(key_pc, scale, prog, bpm, steps, bar_steps)
    
    if num_bars > 1 and bar_steps >= 8:
        last_s0 = (num_bars - 1) * bar_steps
        notes = [n for n in notes if n["step"] < last_s0] # Clear last bar for cadence
        
        final_pc = key_pc
        R_SOP, R_ALT, R_TEN, R_BAS = 5, 4, 3, 2
        
        if mode == "phrygian":
            flat_ii_pc = key_pc + SCALES[scale][1]
            notes.append(mk(last_s0, note_name(flat_ii_pc, R_BAS), "2n", 0.65, steps))
            notes.append(mk(last_s0 + min(8, bar_steps // 2), note_name(final_pc, R_BAS), "2n", 0.70, steps))
            notes.append(mk(last_s0, scale_tone(key_pc, scale, 6, R_SOP), "2n", 0.65, steps))
            notes.append(mk(last_s0 + min(8, bar_steps // 2), scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70, steps))
            notes.append(mk(last_s0, scale_tone(key_pc, scale, 3, R_TEN), "2n", 0.5, steps))
            notes.append(mk(last_s0 + min(8, bar_steps // 2), scale_tone(key_pc, scale, 4, R_TEN), "2n", 0.5, steps))
        else:
            v_pc = key_pc + SCALES[scale][4]
            notes.append(mk(last_s0, note_name(v_pc, R_BAS), "2n", 0.65, steps))
            notes.append(mk(last_s0 + min(8, bar_steps // 2), note_name(final_pc, R_BAS), "2n", 0.70, steps))
            if random.random() < 0.5:
                notes.append(mk(last_s0, scale_tone(key_pc, scale, 6, R_SOP), "4n.", 0.65, steps))
                notes.append(mk(last_s0 + 6, scale_tone(key_pc, scale, 5, R_SOP), "8n", 0.6, steps))
                notes.append(mk(last_s0 + min(8, bar_steps // 2), scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70, steps))
            else:
                notes.append(mk(last_s0, scale_tone(key_pc, scale, 6, R_SOP), "2n", 0.65, steps))
                notes.append(mk(last_s0 + min(8, bar_steps // 2), scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70, steps))
            notes.append(mk(last_s0, scale_tone(key_pc, scale, 1, R_TEN), "2n", 0.5, steps))
            notes.append(mk(last_s0 + min(8, bar_steps // 2), scale_tone(key_pc, scale, 2, R_TEN), "2n", 0.5, steps))
    return notes

