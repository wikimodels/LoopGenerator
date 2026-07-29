import random
import math
from .core import *
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

def prog_neapolitan_minor(key_pc, scale, steps, seg):
    """i–♭II–V–i — Neapolitan chord (chromatic late-Baroque cadence)."""
    v_pc    = (key_pc + 7) % 12      # perfect 5th up = dominant root
    neap_pc = (key_pc + 1) % 12      # ♭II = Neapolitan (half-step above tonic)
    num_seg = steps // seg
    pcs     = [key_pc % 12, neap_pc, v_pc, key_pc % 12]
    quals   = ["min", "maj", "maj", "min"]
    degs    = [0, 0, 4, 0]
    segs_ = []
    for i in range(num_seg):
        idx = i % len(pcs)
        segs_.append({"s0": i * seg, "root_pc": pcs[idx],
                      "quality": quals[idx], "bass_pc": pcs[idx], "deg": degs[idx]})
    return segs_

def prog_descending_thirds_minor(key_pc, scale, steps, seg):
    """i–VI–III–VII — descending-thirds sequence (Bach / Handel idiom)."""
    formula   = [0, 5, 2, 6]
    qualities = ["min", "maj", "maj", "maj"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)

def prog_phrygian_cadence(key_pc, scale, steps, seg):
    """iv–III–II–i — Phrygian descending cadence (strong half-cadence)."""
    formula   = [3, 2, 1, 0]
    qualities = ["min", "maj", "dim", "min"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)

def prog_descending_major(key_pc, scale, steps, seg):
    """I–vii°–vi–V — descending soprano line in major."""
    formula   = [0, 6, 5, 4]
    qualities = ["maj", "dim", "min", "maj"]
    return _baroque_segs(key_pc, "major", steps, seg, formula, qualities)

def prog_royal_fanfare(key_pc, scale, steps, seg):
    """I–IV–V–I–vi–IV–V–I — ceremonial major (Purcell / early Handel)."""
    formula   = [0, 3, 4, 0, 5, 3, 4, 0]
    qualities = ["maj", "maj", "maj", "maj", "min", "maj", "maj", "maj"]
    return _baroque_segs(key_pc, "major", steps, seg, formula, qualities)

def prog_circle_major(key_pc, scale, steps, seg):
    """I–IV–vii°–iii–vi–ii–V–I — circle of fifths descending, major."""
    formula   = [0, 3, 6, 2, 5, 1, 4, 0]
    q_map = {0: "maj", 1: "min", 2: "min", 3: "maj", 4: "maj", 5: "min", 6: "dim"}
    qualities = [q_map[d] for d in formula]
    return _baroque_segs(key_pc, "major", steps, seg, formula, qualities)

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

def _bq_melody_voice(notes, segs, key_pc, scale, steps, octave=5, density=None):
    """Upper melodic voice: richer contour, wider range, ornaments, variable density."""
    prev_mel = None
    if density is None:
        density = random.choice([2, 3, 4])

    for i, seg_d in enumerate(segs):
        s0  = seg_d["s0"]
        deg = seg_d.get("deg", 0)
        seg_end = segs[i + 1]["s0"] if i + 1 < len(segs) else steps
        seg_len = seg_end - s0

        # Wider degree range: two below and six above the chord root degree
        raw = [deg + x for x in (-2, -1, 0, 1, 2, 3, 4, 5, 6)]
        choices = tuple(max(0, d_) for d_ in raw)

        start_idx = carry_start(choices, prev_mel)
        # 20% chance: break continuity and leap to a new register position
        if random.random() < 0.20:
            start_idx = random.randrange(len(choices))

        contour = contour_sequence(density, choices=choices,
                                   start=start_idx,
                                   reversal_bias=0.40, max_run=3)

        step_stride = max(2, seg_len // max(density, 1))

        for k, d in enumerate(contour):
            step = s0 + k * step_stride
            if step >= steps:
                continue

            vel = max(0.30, 0.72 - 0.06 * k + random.uniform(-0.06, 0.06))

            # Grace-note ornament before the first note of each phrase segment
            if k == 0 and step > 0 and random.random() < 0.28:
                grace = scale_tone(key_pc, scale, d + 1, octave)
                notes.append(mk(step - 1, grace, "16n", 0.32, steps))

            note_obj = mk(step, scale_tone(key_pc, scale, d, octave), "4n", vel, steps)

            # Occasionally make a note probabilistic (sparse, breath-like)
            if random.random() < 0.12:
                note_obj["chance"] = round(random.uniform(0.60, 0.85), 2)

            notes.append(note_obj)

        prev_mel = contour[-1]

def _baroque_key_character(key_pc):
    """Map key pitch-class to a character profile that biases texture and density.
    Uses circle-of-fifths grouping so each key has a distinct structural flavor,
    not just a transposition of the same pattern.
    """
    # Spread the 12 keys into 4 groups via circle-of-fifths ordering
    cof_pos = (key_pc * 7) % 12
    group = cof_pos % 4
    profiles = [
        # Group 0 (C, E, G#): bright, energetic — toccata / running passages
        {"textures": ["toccata", "broken_up", "alberti"],        "mel_oct": 5, "density": 4},
        # Group 1 (G, B, D#): lyrical, expressive — sarabande / singing
        {"textures": ["sarabande", "block", "walking"],          "mel_oct": 4, "density": 2},
        # Group 2 (D, F#, A#): driven, dance-like — broken arpeggios
        {"textures": ["broken_updown", "broken_up", "alberti"],  "mel_oct": 5, "density": 3},
        # Group 3 (A, C#, F): deep, mysterious — murky / walking bass
        {"textures": ["murky", "walking", "sarabande"],          "mel_oct": 4, "density": 3},
    ]
    return profiles[group]

def _bq_texture_toccata(notes, s0, seg, root_pc, qual, steps):
    """Running 16th notes — Bach Toccata / Two-Part Invention style."""
    triad = chord_tones(root_pc, qual, 4)
    # Extend with octave note for a longer sweep
    extended = triad + [note_name(root_pc, 5)] + list(reversed(triad))
    for k in range(seg):
        step = s0 + k
        if step >= steps:
            break
        note = extended[k % len(extended)]
        vel = 0.52 + 0.12 * (k % 4 == 0) + random.uniform(-0.03, 0.03)
        notes.append(mk(step, note, "16n", vel, steps))

def _bq_texture_sarabande(notes, s0, seg, root_pc, qual, steps):
    """Sarabande: dotted rhythm with accent on beat 2 (slow Baroque dance)."""
    triad = chord_tones(root_pc, qual, 3)
    if not triad:
        return
    # Beat 1: light downbeat
    notes.append(mk(s0, triad[0 % len(triad)], "4n", 0.38, steps))
    # Beat 2 (step+4): the characteristic sarabande accent
    if s0 + 4 < steps:
        notes.append(mk(s0 + 4, triad[1 % len(triad)], "4n.", 0.68, steps))
    # Beat 3 half (step+10): lighter resolution
    if seg > 8 and s0 + 10 < steps:
        notes.append(mk(s0 + 10, triad[2 % len(triad)], "8n", 0.42, steps))

def gen_baroque(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    """
    Baroque generator v3: authentic progressions x textures x key character.
    Each key_pc has a distinct bias, producing genuinely different results
    across keys while remaining fully random within each call.
    """
    notes = []
    scale = "harmonic_minor" if minor else "major"
    seg = max(2, (beats_per_bar * 4) // 2)   # half-bar segments

    char = _baroque_key_character(key_pc)

    # — Choose progression ——————————————————————————————————————————
    if minor:
        prog_pool = [
            (25, lambda: prog_andalusian(key_pc, scale, steps, seg)),
            (18, lambda: prog_la_folia(key_pc, scale, steps, seg)),
            (13, lambda: prog_romanesca(key_pc, scale, steps, seg)),
            (10, lambda: prog_passamezzo_antico(key_pc, scale, steps, seg)),
            (10, lambda: prog_circle_of_fifths(key_pc, scale, steps, seg)),
            (10, lambda: prog_neapolitan_minor(key_pc, scale, steps, seg)),
            (8,  lambda: prog_descending_thirds_minor(key_pc, scale, steps, seg)),
            (6,  lambda: prog_phrygian_cadence(key_pc, scale, steps, seg)),
        ]
    else:
        prog_pool = [
            (18, lambda: prog_pachelbel(key_pc, scale, steps, seg)),
            (17, lambda: prog_passamezzo_moderno(key_pc, scale, steps, seg)),
            (17, lambda: prog_descending_major(key_pc, scale, steps, seg)),
            (17, lambda: prog_royal_fanfare(key_pc, scale, steps, seg)),
            (16, lambda: prog_circle_major(key_pc, scale, steps, seg)),
            (15, lambda: _baroque_segs(key_pc, scale, steps, seg,
                                        generate_harmony(scale, length=8))),
        ]

    weights_list  = [w for w, _ in prog_pool]
    builders_list = [fn for _, fn in prog_pool]
    prog_fn   = random.choices(builders_list, weights=weights_list, k=1)[0]
    segs_out  = prog_fn()
    if not segs_out:
        return notes

    # — Choose texture ——————————————————————————————————————————
    all_textures = (["alberti", "walking", "broken_up", "broken_down",
                     "murky", "block", "toccata", "sarabande"] if minor else
                    ["alberti", "broken_up", "broken_updown", "block",
                     "murky", "walking", "toccata", "sarabande"])

    # Base weights equal; key character triples its preferred textures
    base_w = {t: 10 for t in all_textures}
    for preferred in char["textures"]:
        if preferred in base_w:
            base_w[preferred] += 20
    tex_names   = list(base_w.keys())
    tex_weights = [base_w[t] for t in tex_names]
    texture = random.choices(tex_names, weights=tex_weights, k=1)[0]

    # — Melody settings ———————————————————————————————————————
    mel_octave = char["mel_oct"]
    if random.random() < 0.30:        # occasionally flip octave
        mel_octave = 4 if mel_octave == 5 else 5
    mel_density = char["density"]
    if random.random() < 0.25:
        mel_density = max(2, mel_density + random.choice([-1, 1]))

    # — Build notes —————————————————————————————————————————————
    prev_pad = None

    if texture == "walking":
        _bq_walking_bass_segs(notes, segs_out, steps, key_pc, scale)

    for seg_d in segs_out:
        s0      = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual    = seg_d["quality"]
        bass_pc = seg_d.get("bass_pc", root_pc)

        if texture != "walking":
            bass_oct = 2 + (1 if random.random() < 0.10 else 0)
            notes.append(mk(s0, note_name(bass_pc, bass_oct), "4n",
                            0.55 + random.uniform(0.0, 0.08), steps))

        if texture == "alberti":
            _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps)
        elif texture in ("broken_up", "broken_down", "broken_updown"):
            direction = {"broken_up": "up", "broken_down": "down",
                         "broken_updown": "up_down"}[texture]
            _bq_texture_broken_arp(notes, s0, seg, root_pc, qual, steps, direction)
        elif texture == "murky":
            _bq_texture_murky(notes, s0, seg, root_pc, steps)
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)
        elif texture == "block":
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)
        elif texture == "walking":
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)
        elif texture == "toccata":
            _bq_texture_toccata(notes, s0, seg, root_pc, qual, steps)
        elif texture == "sarabande":
            _bq_texture_sarabande(notes, s0, seg, root_pc, qual, steps)
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)

    # — Upper melodic voice ——————————————————————————————————————————
    _bq_melody_voice(notes, segs_out, key_pc, scale, steps,
                     octave=mel_octave, density=mel_density)

    return notes

def gen_baroque_passacaglia(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    Baroque Passacaglia / Lament bass.
    Ground bass: chromatic descending tetrachord in octave 2.
    Above: sustained block chords (basso continuo), expressive melody.
    Key character determines register and optional counter-melody.
    Inspired by Purcell's Dido's Lament, Bach's Passacaglia in C minor.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)   # one chord per bar

    char = _baroque_key_character(key_pc)
    # Passacaglia is inherently slow and expressive — prefer lower register
    mel_oct = char["mel_oct"]
    if mel_oct == 5 and random.random() < 0.45:
        mel_oct = 4

    segs = prog_lament_bass(key_pc, scale, steps, seg)
    if not segs:
        return notes

    scale_pcs = SCALES[scale]
    n_scale = len(scale_pcs)

    def best_scale_deg(root_pc_):
        return min(range(n_scale),
                   key=lambda d: (root_pc_ - key_pc - scale_pcs[d]) % 12)

    add_counter = random.random() < 0.40   # sometimes add a counter-melody voice

    prev_pad = None
    prev_mel = None
    prev_ctr = None
    pattern_len = 4

    for i, seg_d in enumerate(segs):
        if i % pattern_len == 0:
            prev_pad = None

        s0      = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual    = seg_d["quality"]
        bass_pc = seg_d.get("bass_pc", root_pc)

        # ── Ground bass: chromatic descending note ────────────────────────
        bass_vel = 0.68 + random.uniform(-0.05, 0.05)
        notes.append(mk(s0, note_name(bass_pc, 2), "4n", bass_vel, steps))
        if seg >= 8:
            notes.append(mk(s0 + seg // 2, note_name(bass_pc, 2), "4n",
                            bass_vel - 0.12, steps))

        # Basso continuo: block chord in octave 3-4
        prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps, anchor_octave=4)
        if seg >= 8:
            prev_pad = _bq_texture_block_chord(notes, s0 + seg // 2, root_pc, qual,
                                                prev_pad, steps, anchor_octave=4)

        # ── Flowing expressive melody ─────────────────────────────────
        chord_deg = best_scale_deg(root_pc)
        raw = [chord_deg + x for x in (-2, -1, 0, 1, 2, 3, 4)]
        mel_choices = tuple(max(0, c) for c in raw)

        num_mel_notes = max(2, seg // 4)
        if random.random() < 0.25:
            num_mel_notes = max(2, num_mel_notes + random.choice([-1, 1]))

        mel_start = carry_start(mel_choices, prev_mel)
        if random.random() < 0.15:
            mel_start = random.randrange(len(mel_choices))

        contour = contour_sequence(num_mel_notes, choices=mel_choices,
                                   start=mel_start,
                                   reversal_bias=0.50, max_run=2)
        step_stride = max(2, seg // max(num_mel_notes, 1))

        for k, d in enumerate(contour):
            step = s0 + k * step_stride
            if step >= steps:
                continue
            vel = max(0.30, 0.65 - 0.04 * k + random.uniform(-0.06, 0.06))
            if k == 0 and step > 0 and random.random() < 0.22:
                notes.append(mk(step - 1, scale_tone(key_pc, scale, d + 1, mel_oct),
                                "16n", 0.30, steps))
            note_obj = mk(step, scale_tone(key_pc, scale, d, mel_oct), "4n", vel, steps)
            if random.random() < 0.10:
                note_obj["chance"] = round(random.uniform(0.65, 0.90), 2)
            notes.append(note_obj)
        prev_mel = contour[-1]

    return notes

def gen_baroque_pachelbel(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    """
    Pachelbel Canon progression: I–V–vi–iii–IV–I–IV–V, major.
    Broken-chord arpeggio or toccata texture — 'crystal' harpsichord sound.
    Key character varies register, texture density, and melody octave.
    """
    notes = []
    scale = "major"
    seg = max(4, beats_per_bar * 4)

    char = _baroque_key_character(key_pc)

    # Texture: arpeggio family or toccata runs — key character biases the choice
    tex_w = {"toccata": 20, "up": 22, "down": 18, "up_down": 20}
    for preferred in char["textures"]:
        if preferred == "toccata":
            tex_w["toccata"] += 18
        elif preferred in ("broken_up", "broken_updown", "alberti"):
            tex_w["up"] += 12
            tex_w["up_down"] += 8
    texture = random.choices(list(tex_w.keys()), weights=list(tex_w.values()), k=1)[0]

    segs = prog_pachelbel(key_pc, scale, steps, seg)
    if not segs:
        return notes

    prev_pad = None
    for seg_d in segs:
        s0      = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual    = seg_d["quality"]

        bass_oct = 2 + (1 if char["mel_oct"] == 4 and random.random() < 0.15 else 0)
        notes.append(mk(s0, note_name(root_pc, bass_oct), "4n",
                        0.58 + random.uniform(-0.05, 0.05), steps))

        if texture == "toccata":
            _bq_texture_toccata(notes, s0, seg, root_pc, qual, steps)
        else:
            _bq_texture_broken_arp(notes, s0, seg, root_pc, qual, steps, texture)

        if random.random() < 0.35 and seg >= 8:
            prev_pad = _bq_texture_block_chord(notes, s0 + seg // 2, root_pc, qual,
                                                prev_pad, steps)

    # Cantabile melody with key-character variety
    mel_density = char["density"]
    if random.random() < 0.30:
        mel_density = max(2, mel_density + random.choice([-1, 1]))
    _bq_melody_voice(notes, segs, key_pc, scale, steps,
                     octave=char["mel_oct"], density=mel_density)

    return notes

def gen_baroque_circle(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    Circle of fifths progression: i–iv–VII–III–VI–ii°–V–i (minor).
    Alberti bass or murky texture — driven, fugue-like feel.
    Key character selects register and two-voice counterpoint octaves.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)

    char = _baroque_key_character(key_pc)

    # Key character biases texture selection
    if char["textures"][0] == "murky":
        texture = random.choices(["alberti", "murky"], weights=[30, 70], k=1)[0]
    elif char["textures"][0] in ("toccata", "broken_up", "broken_updown"):
        texture = random.choices(["alberti", "murky"], weights=[70, 30], k=1)[0]
    else:
        texture = random.choice(["alberti", "murky"])

    segs = prog_circle_of_fifths(key_pc, scale, steps, seg)
    if not segs:
        return notes

    prev_pad = None
    for seg_d in segs:
        s0      = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual    = seg_d["quality"]

        bass_oct = 2 + (1 if char["mel_oct"] == 4 and random.random() < 0.12 else 0)
        notes.append(mk(s0, note_name(root_pc, bass_oct), "4n",
                        0.58 + random.uniform(-0.04, 0.04), steps))

        if texture == "alberti":
            _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps)
        else:
            _bq_texture_murky(notes, s0, seg, root_pc, steps)
            prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)

    # Two-voice counterpoint — register driven by key character
    v1_oct = char["mel_oct"]
    v2_oct = max(3, v1_oct - 1)
    prev_v1, prev_v2 = None, None
    for seg_d in segs:
        s0  = seg_d["s0"]
        deg = seg_d.get("deg", 0)
        c1  = tuple(deg + x for x in (0, 2, 4, 1))
        c2  = tuple(deg + x for x in (1, 3, 5, 2))
        v1 = contour_sequence(2, choices=c1, start=carry_start(c1, prev_v1),
                              reversal_bias=0.45)
        v2 = contour_sequence(2, choices=c2, start=carry_start(c2, prev_v2),
                              reversal_bias=0.45)
        for k, d in enumerate(v1):
            step = s0 + k * (seg // 2)
            if step < steps:
                notes.append(mk(step, scale_tone(key_pc, scale, d, v1_oct),
                                "4n", 0.60 + random.uniform(-0.05, 0.05), steps))
        for k, d in enumerate(v2):
            step = s0 + 2 + k * (seg // 2)
            if step < steps:
                notes.append(mk(step, scale_tone(key_pc, scale, d, v2_oct),
                                "4n", 0.46 + random.uniform(-0.04, 0.04), steps))
        prev_v1 = v1[-1]
        prev_v2 = v2[-1]

    return notes

def gen_baroque_folia(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    La Folia — 8-chord ostinato: i–V–i–VII–III–VII–i–V.
    Fast Alberti bass in harpsichord style (Corelli, Vivaldi).
    Key character varies melody register, density, and occasional toccata runs.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)

    char = _baroque_key_character(key_pc)
    mel_oct = char["mel_oct"]

    segs = prog_la_folia(key_pc, scale, steps, seg)
    if not segs:
        return notes

    for seg_d in segs:
        s0      = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual    = seg_d["quality"]

        bass_oct = 2 + (1 if char["mel_oct"] == 4 and random.random() < 0.10 else 0)
        notes.append(mk(s0, note_name(root_pc, bass_oct), "4n",
                        0.63 + random.uniform(-0.05, 0.05), steps))

        # Fast Alberti or toccata runs depending on key character
        if char["textures"][0] == "toccata" and random.random() < 0.30:
            _bq_texture_toccata(notes, s0, seg, root_pc, qual, steps)
        else:
            _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps)

    # Virtuoso upper voice: wider range, ornaments, key-character density
    mel_density = char["density"]
    if random.random() < 0.30:
        mel_density = max(2, mel_density + random.choice([-1, 1]))

    prev_mel = None
    for i, seg_d in enumerate(segs):
        s0  = seg_d["s0"]
        deg = seg_d.get("deg", 0)
        seg_end = segs[i + 1]["s0"] if i + 1 < len(segs) else steps
        seg_len = seg_end - s0

        raw = [deg + x for x in (-1, 0, 1, 2, 3, 4, 5)]
        choices = tuple(max(0, c) for c in raw)

        start_idx = carry_start(choices, prev_mel)
        if random.random() < 0.18:
            start_idx = random.randrange(len(choices))

        mel_cnt = max(2, seg // 4)
        contour = contour_sequence(mel_cnt, choices=choices,
                                   start=start_idx,
                                   reversal_bias=0.42, max_run=2)
        step_stride = max(2, seg_len // max(mel_cnt, 1))

        for k, d in enumerate(contour):
            step = s0 + k * step_stride
            if step >= steps:
                continue
            vel = max(0.30, 0.62 - 0.02 * k + random.uniform(-0.05, 0.05))
            if k == 0 and step > 0 and random.random() < 0.24:
                notes.append(mk(step - 1, scale_tone(key_pc, scale, d + 1, mel_oct),
                                "16n", 0.28, steps))
            note_obj = mk(step, scale_tone(key_pc, scale, d, mel_oct), "8n", vel, steps)
            if random.random() < 0.10:
                note_obj["chance"] = round(random.uniform(0.65, 0.88), 2)
            notes.append(note_obj)
        prev_mel = contour[-1]

    return notes

