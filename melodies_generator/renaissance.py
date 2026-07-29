import random
import math
from .core import *

# ---------------------------------------------------------------------------
# HARMONY: weighted modal transition tables instead of fixed 4-chord loops.
# Keys/values are scale degrees (0-6). Weights encode modal character:
#  - dorian:      strong i-VII-i motion, bright vi (raised 6th flavor)
#  - phrygian:    gravity toward the characteristic bII, avoid V-i (no leading tone)
#  - mixolydian:  major-flavored I-VII-I, subtonic cadential pull
#  - aeolian/ionian included as fallbacks for flexibility
# ---------------------------------------------------------------------------
_MODAL_TRANSITIONS = {
    "dorian": {
        0: {6: 3, 2: 2, 4: 2, 3: 2, 5: 1},
        2: {4: 2, 6: 2, 0: 2, 3: 1},
        3: {4: 3, 0: 2, 6: 1, 2: 1},
        4: {0: 3, 6: 2, 3: 1},
        5: {6: 2, 0: 2, 4: 1},
        6: {0: 3, 4: 2, 2: 1},
    },
    "phrygian": {
        0: {1: 3, 3: 2, 5: 2, 6: 1},
        1: {0: 2, 3: 2, 4: 1},
        3: {1: 2, 2: 2, 0: 1, 4: 1},
        2: {1: 3, 0: 1},
        4: {3: 2, 1: 1, 0: 1},
        5: {1: 2, 0: 2, 6: 1},
        6: {0: 2, 5: 1},
    },
    "mixolydian": {
        0: {6: 3, 3: 2, 4: 2, 1: 1, 5: 1},
        3: {4: 2, 0: 3, 6: 1},
        4: {0: 3, 3: 1, 6: 1},
        6: {0: 3, 4: 1, 1: 1},
        1: {0: 2, 6: 1, 4: 1},
        5: {0: 2, 6: 1},
    },
    "aeolian": {
        0: {6: 2, 3: 2, 4: 2, 5: 2, 2: 1},
        3: {4: 2, 6: 2, 0: 2},
        4: {0: 3, 5: 1, 3: 1},
        5: {6: 2, 0: 2, 3: 1},
        6: {0: 3, 4: 1},
        2: {4: 2, 3: 2, 0: 1},
    },
    "ionian": {
        0: {4: 3, 3: 2, 5: 2, 2: 1},
        4: {0: 3, 5: 1},
        3: {4: 2, 0: 2, 1: 1},
        5: {1: 2, 3: 1, 0: 1},
        1: {4: 3, 0: 1},
        2: {5: 2, 3: 1},
    },
}

def _weighted_choice(table):
    total = sum(table.values())
    r = random.uniform(0, total)
    upto = 0
    for k, w in table.items():
        upto += w
        if r <= upto:
            return k
    return list(table.keys())[-1]


def _generate_walk(mode, length, start=0):
    """Random-walk progression driven by modal transition weights.
    Falls back to tonic-return if a degree has no defined exits."""
    table = _MODAL_TRANSITIONS.get(mode, _MODAL_TRANSITIONS["aeolian"])
    prog = [start]
    cur = start
    for _ in range(length - 1):
        opts = table.get(cur % 7)
        if not opts:
            cur = 0
        else:
            cur = _weighted_choice(opts)
        prog.append(cur)
    return prog


def _ren_progression(mode, num_bars):
    """
    Produces a harmonic plan for the whole piece as a sequence of PHRASES,
    each phrase a short random walk through the modal transition table,
    giving fresh harmony every generation instead of looping a fixed pattern.
    Phrase lengths vary (2-4 bars) for rhythmic-harmonic asymmetry typical
    of Renaissance phrase structure (elision / phrase extension).
    """
    # 20% fauxbourdon: parallel first-inversion descent, still worth keeping
    # as a distinct sonic color, but now length-matched exactly to num_bars.
    if random.random() < 0.20:
        fb = [0, 6, 5, 4]
        return [fb[i % len(fb)] for i in range(num_bars)]

    prog = []
    remaining = num_bars
    tonic_anchor = 0
    while remaining > 0:
        phrase_len = min(remaining, random.choice([2, 3, 3, 4]))
        phrase = _generate_walk(mode, phrase_len, start=tonic_anchor)
        prog.extend(phrase)
        tonic_anchor = phrase[-1]
        remaining -= phrase_len
    return prog[:num_bars]


# ---------------------------------------------------------------------------
# RHYTHM: broader rhythmic vocabulary, tagged by "energy" so texture builders
# can pick a mood (stately pavane vs animated galliard vs syncopated hemiola)
# ---------------------------------------------------------------------------
_RHYTHM_SETS = {
    "stately": [
        [("2n", 8), ("4n", 4), ("4n", 4)],
        [("4n", 4), ("4n", 4), ("2n", 8)],
        [("1n", 16)],
        [("2n.", 12), ("4n", 4)],
    ],
    "flowing": [
        [("4n.", 6), ("8n", 2), ("4n", 4), ("4n", 4)],
        [("4n", 4), ("8n", 2), ("8n", 2), ("4n", 4), ("4n", 4)],
        [("8n", 2), ("8n", 2), ("4n", 4), ("4n.", 6), ("8n", 2)],
        [("4n", 4), ("4n.", 6), ("8n", 2), ("4n", 4)],
    ],
    "animated": [
        [("8n", 2)] * 8,
        [("8n", 2), ("8n", 2), ("4n", 4), ("8n", 2), ("8n", 2), ("4n", 4)],
        [("8n.", 3), ("16n", 1), ("8n", 2), ("8n", 2), ("4n", 4), ("4n", 4)],
        [("4n", 4), ("8n", 2), ("8n", 2), ("8n", 2), ("8n", 2), ("4n", 4)],
    ],
    "syncopated": [
        [("8n", 2), ("4n", 4), ("8n", 2), ("4n", 4), ("4n", 4)],
        [("4n", 4), ("8n", 2), ("4n", 4), ("8n", 2), ("4n", 4)],
        [("8n", 2), ("4n.", 6), ("8n", 2), ("4n", 4), ("4n", 4)],
    ],
}

def _pick_rhythm_set(bar_steps, energy):
    valid = [r for r in _RHYTHM_SETS[energy] if sum(s for _, s in r) == bar_steps]
    if valid:
        return valid
    # fall back: search other energies before giving up
    for e in _RHYTHM_SETS:
        valid = [r for r in _RHYTHM_SETS[e] if sum(s for _, s in r) == bar_steps]
        if valid:
            return valid
    return [[("4n", 4)] * max(1, bar_steps // 4)]


# ---------------------------------------------------------------------------
# TEXTURE 1: Homophonic block chords (Pavane/Frottola/Chanson)
# ---------------------------------------------------------------------------
def _ren_texture_dance(key_pc, scale, prog, bpm, s0, span, bar_steps, energy):
    notes = []
    bar = s0 // bar_steps
    deg = prog[bar]
    root_pc = key_pc + SCALES[scale][deg % len(SCALES[scale])]
    qual = diatonic_quality(scale, deg)
    chord_ints = CHORD_QUALITIES[qual]

    bar_rhythm = random.choice(_pick_rhythm_set(span, energy))

    step = s0
    for dur, dstep in bar_rhythm:
        if step >= s0 + span:
            break
        notes.append(mk(step, note_name(root_pc, 2), dur, 0.65, s0 + span))
        notes.append(mk(step, note_name(root_pc + random.choice([chord_ints[1], chord_ints[2]]), 3), dur, 0.55, s0 + span))
        notes.append(mk(step, note_name(root_pc + random.choice([chord_ints[1], chord_ints[2]]), 4), dur, 0.55, s0 + span))
        notes.append(mk(step, note_name(root_pc + random.choice([0, chord_ints[1], chord_ints[2]]), 5), dur, 0.65, s0 + span))
        step += dstep
    return notes


# ---------------------------------------------------------------------------
# TEXTURE 2: Point of imitation (Motet style) with variable entry order/interval
# ---------------------------------------------------------------------------
def _ren_texture_motet(key_pc, scale, prog, bpm, s0, span, bar_steps, energy, voice_order=None):
    notes = []
    bar0 = s0 // bar_steps
    num_bars_local = max(1, span // bar_steps)

    mot_rhythm = random.choice(_pick_rhythm_set(bar_steps, energy)) or [("4n", 4), ("4n", 4), ("8n", 2), ("8n", 2), ("2n", 8)]
    mot_offsets = contour_sequence(len(mot_rhythm), choices=(0, 1, 2, 3, 4, -1, -2), max_run=2)

    all_voice_defs = {
        "Soprano": 5, "Alto": 4, "Tenor": 3, "Bass": 2,
    }
    if voice_order is None:
        names = list(all_voice_defs.keys())
        random.shuffle(names)
        voice_order = names[:random.choice([3, 4])]  # sometimes drop to a trio (duo/trio textures)

    voices = [{"name": n, "reg": all_voice_defs[n], "delay_bars": i} for i, n in enumerate(voice_order)]

    for v in voices:
        prev_deg = None
        for bar in range(num_bars_local):
            gbar = bar0 + bar
            if gbar >= len(prog) or bar < v["delay_bars"]:
                continue
            deg = prog[gbar]
            bs0 = s0 + bar * bar_steps
            if bar == v["delay_bars"]:
                step = bs0
                for (dur, dstep), off in zip(mot_rhythm, mot_offsets):
                    if step >= s0 + span:
                        break
                    notes.append(mk(step, scale_tone(key_pc, scale, deg + off, v["reg"]), dur, 0.6, s0 + span))
                    step += dstep
                prev_deg = deg + mot_offsets[-1]
            else:
                choices = (deg, deg + 1, deg - 1, deg + 2, deg - 2)
                contour = contour_sequence(3, choices=choices, start=carry_start(choices, prev_deg))
                step = bs0
                notes.append(mk(step, scale_tone(key_pc, scale, contour[0], v["reg"]), "2n", 0.55, s0 + span))
                if bar_steps > 4:
                    notes.append(mk(step + min(8, bar_steps // 2), scale_tone(key_pc, scale, contour[1], v["reg"]), "4n", 0.5, s0 + span))
                prev_deg = contour[-1]
    return notes


# ---------------------------------------------------------------------------
# TEXTURE 3: Flowing counterpoint with real 4-3 / 7-6 suspensions
# ---------------------------------------------------------------------------
def _ren_texture_counterpoint(key_pc, scale, prog, bpm, s0, span, bar_steps, energy, carry):
    notes = []
    bar = s0 // bar_steps
    if bar >= len(prog):
        deg = prog[-1]
    else:
        deg = prog[bar]
    
    bas_prev, ten_prev, alt_prev, sop_prev = carry

    bas_choices = (deg, deg + 1, deg - 1)
    bas_idx = carry_start(bas_choices, bas_prev)
    bas_val = bas_choices[bas_idx if bas_idx is not None else 0]

    use_suspension = random.random() < 0.35 and bar_steps >= 8

    if random.random() < 0.3 and bar_steps >= 8:
        notes.append(mk(s0, scale_tone(key_pc, scale, bas_val, 2), "4n", 0.6, s0 + span))
        notes.append(mk(s0 + 4, scale_tone(key_pc, scale, bas_val - 1, 2), "4n", 0.5, s0 + span))
        notes.append(mk(s0 + 8, scale_tone(key_pc, scale, bas_val, 2), "2n", 0.6, s0 + span))
    else:
        notes.append(mk(s0, scale_tone(key_pc, scale, bas_val, 2), "1n" if bar_steps == 16 else "2n", 0.6, s0 + span))
    bas_prev = bas_val

    ten_choices = (deg + 2, deg + 4, deg)
    ten_idx = carry_start(ten_choices, ten_prev)
    ten_val = ten_choices[ten_idx if ten_idx is not None else 0]
    notes.append(mk(s0, scale_tone(key_pc, scale, ten_val, 3), "4n.", 0.55, s0 + span))
    notes.append(mk(s0 + 6, scale_tone(key_pc, scale, ten_val - 1, 3), "8n", 0.5, s0 + span))
    if bar_steps >= 8:
        notes.append(mk(s0 + 8, scale_tone(key_pc, scale, ten_val, 3), "2n", 0.55, s0 + span))
    ten_prev = ten_val

    alt_choices = (deg + 4, deg + 2, deg + 6)
    alt_idx = carry_start(alt_choices, alt_prev)
    alt_val = alt_choices[alt_idx if alt_idx is not None else 0]

    if use_suspension and bar_steps >= 8:
        # hold the alto tone from the outgoing chord (a 4th or 7th above the
        # NEW bass) on the downbeat, then resolve stepwise down at the half-bar
        susp_tone = alt_val + 1  # dissonant suspended tone against new harmony
        notes.append(mk(s0, scale_tone(key_pc, scale, susp_tone, 4), "4n", 0.5, s0 + span))
        notes.append(mk(s0 + 4, scale_tone(key_pc, scale, alt_val, 4), "2n", 0.5, s0 + span))
    else:
        notes.append(mk(s0, scale_tone(key_pc, scale, alt_val, 4), "2n", 0.5, s0 + span))
        if bar_steps >= 8:
            notes.append(mk(s0 + 8, scale_tone(key_pc, scale, alt_val - 1, 4), "2n", 0.5, s0 + span))
    alt_prev = alt_val - 1

    sop_choices = (deg, deg + 2, deg + 4, deg + 7)
    sop_idx = carry_start(sop_choices, sop_prev)
    sop_val = sop_choices[sop_idx if sop_idx is not None else 0]

    if sop_prev is not None and random.random() < 0.5:
        notes.append(mk(s0, scale_tone(key_pc, scale, sop_prev, 5), "4n", 0.65, s0 + span))
        notes.append(mk(s0 + 4, scale_tone(key_pc, scale, sop_val, 5), "4n", 0.6, s0 + span))
        if bar_steps >= 8:
            notes.append(mk(s0 + 8, scale_tone(key_pc, scale, sop_val + 1, 5), "2n", 0.6, s0 + span))
        sop_prev = sop_val + 1
    else:
        notes.append(mk(s0, scale_tone(key_pc, scale, sop_val, 5), "4n", 0.6, s0 + span))
        notes.append(mk(s0 + 4, scale_tone(key_pc, scale, sop_val + 1, 5), "4n", 0.6, s0 + span))
        if bar_steps >= 8:
            notes.append(mk(s0 + 8, scale_tone(key_pc, scale, sop_val - 1, 5), "2n", 0.6, s0 + span))
        sop_prev = sop_val - 1

    return notes, (bas_prev, ten_prev, alt_prev, sop_prev)


# ---------------------------------------------------------------------------
# CADENCES: authentic, plagal, deceptive, phrygian, half — chosen by context.
# Internal phrase-ends may use half/deceptive cadences for structural variety;
# only the final bar gets a full authentic/plagal/phrygian close.
# ---------------------------------------------------------------------------
def _apply_cadence(notes, key_pc, scale, mode, last_s0, bar_steps, steps, kind):
    R_SOP, R_ALT, R_TEN, R_BAS = 5, 4, 3, 2
    half = min(8, bar_steps // 2)
    final_pc = key_pc

    if kind == "phrygian" or mode == "phrygian":
        flat_ii_pc = key_pc + SCALES[scale][1]
        notes.append(mk(last_s0, note_name(flat_ii_pc, R_BAS), "2n", 0.65, steps))
        notes.append(mk(last_s0 + half, note_name(final_pc, R_BAS), "2n", 0.70, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 6, R_SOP), "2n", 0.65, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 3, R_TEN), "2n", 0.5, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 4, R_TEN), "2n", 0.5, steps))

    elif kind == "plagal":
        iv_pc = key_pc + SCALES[scale][3]
        notes.append(mk(last_s0, note_name(iv_pc, R_BAS), "2n", 0.6, steps))
        notes.append(mk(last_s0 + half, note_name(final_pc, R_BAS), "2n", 0.7, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 5, R_SOP), "2n", 0.6, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.7, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 1, R_TEN), "2n", 0.5, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 0, R_TEN), "2n", 0.5, steps))

    elif kind == "deceptive":
        v_pc = key_pc + SCALES[scale][4]
        vi_pc = key_pc + SCALES[scale][5]
        notes.append(mk(last_s0, note_name(v_pc, R_BAS), "2n", 0.6, steps))
        notes.append(mk(last_s0 + half, note_name(vi_pc, R_BAS), "2n", 0.65, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 6, R_SOP), "2n", 0.6, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 7, R_SOP), "2n", 0.65, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 1, R_TEN), "2n", 0.5, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 2, R_TEN), "2n", 0.5, steps))

    elif kind == "half":
        v_pc = key_pc + SCALES[scale][4]
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 0, R_BAS), "4n", 0.55, steps))
        notes.append(mk(last_s0 + half, note_name(v_pc, R_BAS), "2n", 0.6, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 4, R_SOP), "4n", 0.55, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 6, R_SOP), "2n", 0.6, steps))

    else:  # "authentic" — V-I with musica ficta (raised leading tone) option
        v_pc = key_pc + SCALES[scale][4]
        notes.append(mk(last_s0, note_name(v_pc, R_BAS), "2n", 0.65, steps))
        notes.append(mk(last_s0 + half, note_name(final_pc, R_BAS), "2n", 0.70, steps))
        # musica ficta: raise the 7th degree by a semitone into the final chord
        leading_tone_pc = key_pc + SCALES[scale][6] + 1
        if random.random() < 0.5:
            notes.append(mk(last_s0, note_name(leading_tone_pc, R_SOP), "4n.", 0.65, steps))
            notes.append(mk(last_s0 + 6, scale_tone(key_pc, scale, 5, R_SOP), "8n", 0.6, steps))
            notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70, steps))
        else:
            notes.append(mk(last_s0, note_name(leading_tone_pc, R_SOP), "2n", 0.65, steps))
            notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 0, R_SOP), "2n", 0.70, steps))
        notes.append(mk(last_s0, scale_tone(key_pc, scale, 1, R_TEN), "2n", 0.5, steps))
        notes.append(mk(last_s0 + half, scale_tone(key_pc, scale, 2, R_TEN), "2n", 0.5, steps))

    return notes


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------
def gen_renaissance(key_pc, scale_name, bpm, steps, beats_per_bar=4, mode="dorian"):
    scale = mode
    bar_steps = beats_per_bar * 4
    num_bars = max(1, steps // bar_steps)

    prog = _ren_progression(mode, num_bars)

    # overall energy for the piece (affects rhythmic vocabulary throughout)
    energy = random.choice(["stately", "flowing", "animated", "syncopated"])

    # Section plan: chop the piece into 2-4 bar sections and assign a texture
    # to each, giving contrast (imitative point -> homophonic cadence, etc.)
    # instead of one texture for the whole piece.
    texture_fns = ["dance", "motet", "counterpoint"]
    sections = []
    b = 0
    prev_choice = None
    while b < num_bars:
        length = min(num_bars - b, random.choice([2, 2, 3, 4]))
        choice = random.choice([t for t in texture_fns if t != prev_choice] or texture_fns)
        sections.append((b, length, choice))
        prev_choice = choice
        b += length

    notes = []
    cp_carry = (None, None, None, None)  # bass/tenor/alto/soprano memory across counterpoint sections

    for (start_bar, length, texture) in sections:
        s0 = start_bar * bar_steps
        span = length * bar_steps
        if texture == "dance":
            for bi in range(length):
                notes.extend(_ren_texture_dance(key_pc, scale, prog, bpm, s0 + bi * bar_steps, bar_steps, bar_steps, energy))
        elif texture == "motet":
            notes.extend(_ren_texture_motet(key_pc, scale, prog, bpm, s0, span, bar_steps, energy))
        else:  # counterpoint, bar by bar to keep suspensions in phase
            for bi in range(length):
                bar_notes, cp_carry = _ren_texture_counterpoint(
                    key_pc, scale, prog, bpm, s0 + bi * bar_steps, bar_steps, bar_steps, energy, cp_carry
                )
                notes.extend(bar_notes)

    # Internal phrase-end cadences: at each section boundary (except the very
    # last bar, which gets the final close below) occasionally stamp a light
    # half/deceptive cadence flavor by nudging the harmony -- purely additive,
    # doesn't remove existing section notes, just reinforces phrase endings.
    if num_bars > 4 and bar_steps >= 8:
        for (start_bar, length, _texture) in sections[:-1]:
            end_bar = start_bar + length
            if end_bar >= num_bars - 1:
                continue
            if random.random() < 0.35:
                cadence_kind = random.choice(["half", "deceptive"])
                boundary_s0 = (end_bar - 1) * bar_steps
                notes = [n for n in notes if not (boundary_s0 <= n["step"] < boundary_s0 + bar_steps)]
                notes = _apply_cadence(notes, key_pc, scale, mode, boundary_s0, bar_steps, steps, cadence_kind)

    # Final cadence: full authentic/plagal/phrygian close, replacing last bar.
    if num_bars > 1 and bar_steps >= 8:
        last_s0 = (num_bars - 1) * bar_steps
        notes = [n for n in notes if n["step"] < last_s0]

        if mode == "phrygian":
            final_kind = "phrygian"
        else:
            final_kind = random.choices(
                ["authentic", "plagal"], weights=[70, 30]
            )[0]

        notes = _apply_cadence(notes, key_pc, scale, mode, last_s0, bar_steps, steps, final_kind)

    return notes
