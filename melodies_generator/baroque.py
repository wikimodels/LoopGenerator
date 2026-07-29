import random
import math
from .core import *

# =============================================================================
# PROGRESSION BUILDERS — unchanged formulas (still historically grounded),
# plus a new weighted-walk generator for minor to match the major-side
# `generate_harmony` and stop minor from being 100% fixed-formula.
# =============================================================================

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
    """i–VII–VI–V(major) — Andalusian cadence: Am–G–F–E."""
    formula   = [0, 6, 5, 4]
    qualities = ["min", "maj", "maj", "maj"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)

def prog_lament_bass(key_pc, scale, steps, seg, minor=True):
    """Chromatic descending tetrachord (passacaglia / lament bass)."""
    hm_scale = "harmonic_minor"
    chromatic_offsets = [0, -1, -2, -5]
    v_root_pc = (key_pc + SCALES[hm_scale][4]) % 12

    def _harm(step_idx):
        if step_idx % len(chromatic_offsets) < 3:
            return key_pc % 12, "min"
        else:
            return v_root_pc, "maj"

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
    """La Folia 8-chord cycle: i–V–i–VII–III–VII–i–V."""
    formula   = [0, 4, 0, 6, 2, 6, 0, 4]
    qualities = ["min","maj","min","maj","maj","maj","min","maj"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)

def prog_romanesca(key_pc, scale, steps, seg, minor=True):
    """III–VII–i–V — Romanesca (early baroque)."""
    formula   = [2, 6, 0, 4]
    qualities = ["maj", "maj", "min", "maj"]
    return _baroque_segs(key_pc, "natural_minor", steps, seg, formula, qualities)

def prog_passamezzo_antico(key_pc, scale, steps, seg, minor=True):
    """i–VII–i–V–III–VII–i–V–i — Passamezzo antico (extended 9-chord)."""
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
    v_pc    = (key_pc + 7) % 12
    neap_pc = (key_pc + 1) % 12
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


# -----------------------------------------------------------------------
# NEW: weighted-walk minor harmony generator, mirroring `generate_harmony`
# on the major side. Gives the minor prog_pool a genuinely non-fixed option
# instead of relying solely on 8 scripted formulas.
# -----------------------------------------------------------------------
_MINOR_TRANSITIONS = {
    # degrees in harmonic_minor; weighted toward authentic baroque motion
    # (strong iv/V pull, functional predominant->dominant->tonic chains)
    0: {3: 3, 5: 2, 1: 2, 4: 2, 2: 1, 6: 1},
    1: {4: 3, 6: 2, 0: 1},
    2: {5: 3, 1: 2, 0: 2, 3: 1},
    3: {4: 3, 6: 2, 0: 2, 1: 1},
    4: {0: 4, 5: 1, 3: 1},
    5: {1: 2, 3: 2, 4: 2, 0: 1},
    6: {0: 3, 4: 2},
}

_MINOR_QUALITY_MAP = {0: "min", 1: "dim", 2: "maj", 3: "min", 4: "maj", 5: "maj", 6: "dim"}

def _weighted_choice(table):
    total = sum(table.values())
    r = random.uniform(0, total)
    upto = 0
    for k, w in table.items():
        upto += w
        if r <= upto:
            return k
    return list(table.keys())[-1]

def generate_harmony_minor(scale="harmonic_minor", length=8, start=0):
    """Random-walk minor progression through functional degree weights.
    Returns a plain degree list (compatible with `_baroque_segs` formula arg);
    caller supplies qualities via `_MINOR_QUALITY_MAP` or passes None to let
    `_baroque_segs` derive quality from `build_diatonic_chord`.
    """
    prog = [start]
    cur = start
    for _ in range(length - 1):
        opts = _MINOR_TRANSITIONS.get(cur % 7)
        cur = _weighted_choice(opts) if opts else 0
        prog.append(cur)
    # ensure it resolves home for a satisfying loop point
    if prog[-1] != 0 and random.random() < 0.6:
        prog.append(0)
    return prog

def prog_generated_minor(key_pc, scale, steps, seg):
    degrees = generate_harmony_minor(length=random.choice([6, 8, 8, 10]))
    qualities = [_MINOR_QUALITY_MAP[d % 7] for d in degrees]
    return _baroque_segs(key_pc, "harmonic_minor", steps, seg, degrees, qualities)


# =============================================================================
# ACCOMPANIMENT TEXTURES — now each with multiple rhythmic/figuration variants
# instead of one hardcoded pattern, selected once per *section* rather than
# reused identically for the whole piece.
# =============================================================================

_ALBERTI_PATTERNS = [
    [0, 2, 1, 2],   # classic root-fifth-third-fifth
    [0, 1, 2, 1],   # root-third-fifth-third
    [0, 2, 1, 0],   # root-fifth-third-root (more grounded)
    [0, 1, 2, 0, 1, 2, 2, 1],  # 8-slot extended variant (used when seg allows)
]

def _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps):
    """Alberti bass with a randomly chosen figuration pattern per call."""
    triad = chord_tones(root_pc, qual, 3)
    if len(triad) < 3:
        triad = triad + [triad[-1]]
    n_slots = seg // 2
    pattern = random.choice([p for p in _ALBERTI_PATTERNS if len(p) <= max(n_slots, 4)] or [_ALBERTI_PATTERNS[0]])
    for k in range(n_slots):
        step = s0 + k * 2
        idx = pattern[k % len(pattern)]
        notes.append(mk(step, triad[idx % len(triad)], "8n", 0.45 + 0.05 * (k % 4 == 0), steps))

def _bq_texture_broken_arp(notes, s0, seg, root_pc, qual, steps, direction="up"):
    """Broken chord arpeggio with a few contour variants beyond plain up/down."""
    triad = chord_tones(root_pc, qual, 3)
    extended = triad + [note_name(root_pc, 4)]
    variant = random.random()
    if direction == "down":
        extended = list(reversed(extended))
    elif direction == "up_down":
        extended = triad + list(reversed(triad))
    elif direction == "up" and variant < 0.25:
        # occasional skip pattern: root-fifth-third-octave instead of straight run
        if len(triad) >= 3:
            extended = [triad[0], triad[2], triad[1], note_name(root_pc, 4)]
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

def _bq_texture_toccata(notes, s0, seg, root_pc, qual, steps):
    """Running 16th notes — Bach Toccata / Two-Part Invention style,
    with a couple of contour variants for run direction."""
    triad = chord_tones(root_pc, qual, 4)
    style = random.random()
    if style < 0.6:
        extended = triad + [note_name(root_pc, 5)] + list(reversed(triad))
    elif style < 0.85:
        extended = list(reversed(triad)) + [note_name(root_pc, 4)] + triad
    else:
        # wave contour: up-down-up
        extended = triad + list(reversed(triad)) + triad
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
    notes.append(mk(s0, triad[0 % len(triad)], "4n", 0.38, steps))
    if s0 + 4 < steps:
        notes.append(mk(s0 + 4, triad[1 % len(triad)], "4n.", 0.68, steps))
    if seg > 8 and s0 + 10 < steps:
        notes.append(mk(s0 + 10, triad[2 % len(triad)], "8n", 0.42, steps))

def _bq_walking_bass_segs(notes, segs, steps, key_pc, scale):
    """Walking bass: stepwise movement between chord roots, one note per half-beat."""
    scale_pcs = SCALES[scale]
    n_scale = len(scale_pcs)
    for idx, seg_d in enumerate(segs):
        s0 = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        next_root_pc = segs[(idx + 1) % len(segs)]["root_pc"]
        best_deg = min(range(n_scale), key=lambda d: (root_pc - key_pc - scale_pcs[d]) % 12)
        seg_len = (segs[idx + 1]["s0"] if idx + 1 < len(segs) else steps) - s0
        n_steps = seg_len // 4
        for b in range(n_steps):
            if b == 0:
                bass_pc = root_pc
            elif b == n_steps - 1:
                diff = (next_root_pc - root_pc) % 12
                bass_pc = (root_pc + diff - 1) % 12 if diff > 0 else (root_pc - 1) % 12
            else:
                step_deg = (best_deg + b) % n_scale
                bass_pc = (key_pc + scale_pcs[step_deg]) % 12
            step = s0 + b * 4
            if step < steps:
                notes.append(mk(step, note_name(bass_pc, 2), "4n", 0.58 + 0.07 * (b == 0), steps))

def _bq_melody_voice(notes, segs, key_pc, scale, steps, octave=5, density=None):
    """Upper melodic voice: richer contour, wider range, ornaments, variable
    density, and occasional chromatic passing tones between contour notes."""
    prev_mel = None
    if density is None:
        density = random.choice([2, 3, 4])

    for i, seg_d in enumerate(segs):
        s0  = seg_d["s0"]
        deg = seg_d.get("deg", 0)
        seg_end = segs[i + 1]["s0"] if i + 1 < len(segs) else steps
        seg_len = seg_end - s0

        raw = [deg + x for x in (-2, -1, 0, 1, 2, 3, 4, 5, 6)]
        choices = tuple(max(0, d_) for d_ in raw)

        start_idx = carry_start(choices, prev_mel)
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

            if k == 0 and step > 0 and random.random() < 0.28:
                grace = scale_tone(key_pc, scale, d + 1, octave)
                notes.append(mk(step - 1, grace, "16n", 0.32, steps))

            note_obj = mk(step, scale_tone(key_pc, scale, d, octave), "4n", vel, steps)

            if random.random() < 0.12:
                note_obj["chance"] = round(random.uniform(0.60, 0.85), 2)

            notes.append(note_obj)

            # Occasional chromatic passing tone bridging to the next contour note
            if (k + 1 < len(contour) and step_stride >= 3
                    and random.random() < 0.10 and step + step_stride - 1 < steps):
                next_d = contour[k + 1]
                if abs(next_d - d) >= 2:
                    direction = 1 if next_d > d else -1
                    pass_pc = (key_pc + SCALES[scale][d % len(SCALES[scale])] + direction) % 12
                    notes.append(mk(step + step_stride - 1, note_name(pass_pc, octave),
                                    "16n", vel - 0.1, steps))

        prev_mel = contour[-1]


# =============================================================================
# KEY CHARACTER — expanded to 8 distinct profiles (was effectively 4),
# grouped by true circle-of-fifths distance from C so neighboring keys on
# the circle share family resemblance while opposite keys contrast sharply.
# =============================================================================

def _baroque_key_character(key_pc):
    """Map key pitch-class to a character profile that biases texture and
    density. Groups keys by circle-of-fifths distance from C (mod 12, via
    the fifths-generator 7), split into 8 profiles for real per-key variety
    instead of the previous 4-bucket scheme.
    """
    # position of key_pc around the circle of fifths, 0..11
    # (multiply by the modular inverse of 7 mod 12, which is 7 itself,
    # since 7*7=49=48+1 => 7 is self-inverse mod 12)
    cof_pos = (key_pc * 7) % 12
    group = cof_pos % 8

    profiles = [
        {"textures": ["toccata", "broken_up", "alberti"],       "mel_oct": 5, "density": 4},
        {"textures": ["sarabande", "block", "walking"],         "mel_oct": 4, "density": 2},
        {"textures": ["broken_updown", "broken_up", "alberti"], "mel_oct": 5, "density": 3},
        {"textures": ["murky", "walking", "sarabande"],         "mel_oct": 4, "density": 3},
        {"textures": ["alberti", "toccata", "broken_down"],     "mel_oct": 5, "density": 3},
        {"textures": ["block", "sarabande", "murky"],           "mel_oct": 3, "density": 2},
        {"textures": ["broken_up", "walking", "toccata"],       "mel_oct": 4, "density": 4},
        {"textures": ["murky", "alberti", "broken_updown"],     "mel_oct": 4, "density": 3},
    ]
    return profiles[group]


# =============================================================================
# SECTION PLANNING — shared helper so every gen_* function can chop its
# segment list into contiguous chunks and assign varying textures/params
# per chunk instead of one static choice for the whole piece.
# =============================================================================

def _plan_sections(num_segs, min_len=2, max_len=4):
    """Split `num_segs` segments into contiguous sections of varying length."""
    sections = []
    i = 0
    while i < num_segs:
        length = min(num_segs - i, random.randint(min_len, max_len))
        sections.append((i, length))
        i += length
    return sections


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def gen_baroque(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=False):
    """
    Baroque generator v4: authentic progressions x sectioned textures x
    expanded key character. Textures now vary *within* a piece by section
    (2-4 segments per section) rather than staying fixed for the whole track,
    and minor keys can draw from a generative weighted-walk progression too.
    """
    notes = []
    scale = "harmonic_minor" if minor else "major"
    seg = max(2, (beats_per_bar * 4) // 2)

    char = _baroque_key_character(key_pc)

    if minor:
        prog_pool = [
            (22, lambda: prog_andalusian(key_pc, scale, steps, seg)),
            (16, lambda: prog_la_folia(key_pc, scale, steps, seg)),
            (12, lambda: prog_romanesca(key_pc, scale, steps, seg)),
            (9,  lambda: prog_passamezzo_antico(key_pc, scale, steps, seg)),
            (9,  lambda: prog_circle_of_fifths(key_pc, scale, steps, seg)),
            (9,  lambda: prog_neapolitan_minor(key_pc, scale, steps, seg)),
            (7,  lambda: prog_descending_thirds_minor(key_pc, scale, steps, seg)),
            (6,  lambda: prog_phrygian_cadence(key_pc, scale, steps, seg)),
            (14, lambda: prog_generated_minor(key_pc, scale, steps, seg)),
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

    all_textures = (["alberti", "walking", "broken_up", "broken_down",
                     "murky", "block", "toccata", "sarabande"] if minor else
                    ["alberti", "broken_up", "broken_updown", "block",
                     "murky", "walking", "toccata", "sarabande"])

    base_w = {t: 10 for t in all_textures}
    for preferred in char["textures"]:
        if preferred in base_w:
            base_w[preferred] += 20
    tex_names   = list(base_w.keys())
    tex_weights = [base_w[t] for t in tex_names]

    # --- Sectioned texture plan: pick a texture per 2-4 segment chunk,
    # avoiding immediate repeats so the piece actually shifts character.
    sections = _plan_sections(len(segs_out), min_len=2, max_len=4)
    section_textures = []
    prev_tex = None
    for _s0, _len in sections:
        choices = [t for t in tex_names if t != prev_tex] or tex_names
        weights = [base_w[t] for t in choices]
        tex = random.choices(choices, weights=weights, k=1)[0]
        section_textures.append(tex)
        prev_tex = tex

    mel_octave = char["mel_oct"]
    if random.random() < 0.30:
        mel_octave = 4 if mel_octave == 5 else 5
    mel_density = char["density"]
    if random.random() < 0.25:
        mel_density = max(2, mel_density + random.choice([-1, 1]))

    prev_pad = None

    for (start_idx, length), texture in zip(sections, section_textures):
        section_segs = segs_out[start_idx:start_idx + length]

        if texture == "walking":
            _bq_walking_bass_segs(notes, section_segs, steps, key_pc, scale)

        for seg_d in section_segs:
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

    _bq_melody_voice(notes, segs_out, key_pc, scale, steps,
                     octave=mel_octave, density=mel_density)

    return notes


# =============================================================================
# STANDALONE FORM GENERATORS
# Each is called independently elsewhere, so signatures/names are preserved
# exactly. All now vary their accompaniment texture by section rather than
# locking one texture for the entire piece.
# =============================================================================

def gen_baroque_passacaglia(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    Baroque Passacaglia / Lament bass.
    Ground bass: chromatic descending tetrachord in octave 2 (unchanged —
    this is the defining structural device of the form and must stay fixed).
    Above: basso continuo alternates between block-chord and a sparser
    "drone-like" pad by section for some textural contrast across repeats,
    and the counter-melody's register/ornament density vary with key character.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)

    char = _baroque_key_character(key_pc)
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

    # Section plan over 4-bar ground-bass repeats: every repeat of the pattern
    # (length 4) is one "section" that can pick a different continuo color.
    pattern_len = 4
    num_patterns = max(1, len(segs) // pattern_len)
    continuo_styles = []
    prev_style = None
    for _ in range(num_patterns):
        choices = [s for s in ("block", "block_low", "drone") if s != prev_style]
        style = random.choice(choices)
        continuo_styles.append(style)
        prev_style = style

    prev_pad = None
    prev_mel = None

    for i, seg_d in enumerate(segs):
        pattern_idx = i // pattern_len
        style = continuo_styles[min(pattern_idx, len(continuo_styles) - 1)]

        if i % pattern_len == 0:
            prev_pad = None

        s0      = seg_d["s0"]
        root_pc = seg_d["root_pc"]
        qual    = seg_d["quality"]
        bass_pc = seg_d.get("bass_pc", root_pc)

        bass_vel = 0.68 + random.uniform(-0.05, 0.05)
        notes.append(mk(s0, note_name(bass_pc, 2), "4n", bass_vel, steps))
        if seg >= 8:
            notes.append(mk(s0 + seg // 2, note_name(bass_pc, 2), "4n",
                            bass_vel - 0.12, steps))

        anchor_oct = 3 if style == "block_low" else 4
        prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps, anchor_octave=anchor_oct)
        if seg >= 8:
            if style == "drone":
                _bq_texture_drone(notes, s0 + seg // 2, seg // 2, key_pc % 12, root_pc, qual, steps)
            else:
                prev_pad = _bq_texture_block_chord(notes, s0 + seg // 2, root_pc, qual,
                                                    prev_pad, steps, anchor_octave=anchor_oct)

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
    Accompaniment now varies by section between toccata runs and broken-chord
    arpeggios (up/down/up-down) instead of locking one texture for the whole
    canon — canons traditionally build in figural intensity over repeats.
    """
    notes = []
    scale = "major"
    seg = max(4, beats_per_bar * 4)

    char = _baroque_key_character(key_pc)

    tex_w = {"toccata": 20, "up": 22, "down": 18, "up_down": 20}
    for preferred in char["textures"]:
        if preferred == "toccata":
            tex_w["toccata"] += 18
        elif preferred in ("broken_up", "broken_updown", "alberti"):
            tex_w["up"] += 12
            tex_w["up_down"] += 8

    segs = prog_pachelbel(key_pc, scale, steps, seg)
    if not segs:
        return notes

    sections = _plan_sections(len(segs), min_len=2, max_len=3)
    section_textures = []
    prev_tex = None
    for _s0, _len in sections:
        choices = [t for t in tex_w if t != prev_tex] or list(tex_w.keys())
        weights = [tex_w[t] for t in choices]
        tex = random.choices(choices, weights=weights, k=1)[0]
        section_textures.append(tex)
        prev_tex = tex

    prev_pad = None
    for (start_idx, length), texture in zip(sections, section_textures):
        for seg_d in segs[start_idx:start_idx + length]:
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

    mel_density = char["density"]
    if random.random() < 0.30:
        mel_density = max(2, mel_density + random.choice([-1, 1]))
    _bq_melody_voice(notes, segs, key_pc, scale, steps,
                     octave=char["mel_oct"], density=mel_density)

    return notes


def gen_baroque_circle(key_pc, scale_name, bpm, steps, beats_per_bar=4, minor=True):
    """
    Circle of fifths progression: i–iv–VII–III–VI–ii°–V–i (minor).
    Bass texture now alternates between Alberti and murky by section rather
    than committing to one for the whole descent, and the two-voice
    counterpoint above shifts contour choices per section for variety.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)

    char = _baroque_key_character(key_pc)

    if char["textures"][0] == "murky":
        tex_w = {"alberti": 30, "murky": 70}
    elif char["textures"][0] in ("toccata", "broken_up", "broken_updown"):
        tex_w = {"alberti": 70, "murky": 30}
    else:
        tex_w = {"alberti": 50, "murky": 50}

    segs = prog_circle_of_fifths(key_pc, scale, steps, seg)
    if not segs:
        return notes

    sections = _plan_sections(len(segs), min_len=2, max_len=3)
    section_textures = []
    prev_tex = None
    for _s0, _len in sections:
        choices = [t for t in tex_w if t != prev_tex] or list(tex_w.keys())
        weights = [tex_w[t] for t in choices]
        tex = random.choices(choices, weights=weights, k=1)[0]
        section_textures.append(tex)
        prev_tex = tex

    prev_pad = None
    for (start_idx, length), texture in zip(sections, section_textures):
        for seg_d in segs[start_idx:start_idx + length]:
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

    v1_oct = char["mel_oct"]
    v2_oct = max(3, v1_oct - 1)
    prev_v1, prev_v2 = None, None

    # per-section contour interval sets for the counterpoint pair, so the
    # two-voice writing doesn't lock into the same shape every segment
    contour_variants = [
        ((0, 2, 4, 1), (1, 3, 5, 2)),
        ((0, 1, 3, 2), (2, 3, 5, 4)),
        ((0, 2, 3, 5), (1, 2, 4, 3)),
    ]

    for (start_idx, length), _tex in zip(sections, section_textures):
        c1, c2 = random.choice(contour_variants)
        for seg_d in segs[start_idx:start_idx + length]:
            s0  = seg_d["s0"]
            deg = seg_d.get("deg", 0)
            cc1 = tuple(deg + x for x in c1)
            cc2 = tuple(deg + x for x in c2)
            v1 = contour_sequence(2, choices=cc1, start=carry_start(cc1, prev_v1),
                                  reversal_bias=0.45)
            v2 = contour_sequence(2, choices=cc2, start=carry_start(cc2, prev_v2),
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
    Bass figuration now varies by section between Alberti and toccata runs
    (weighted by key character) instead of a single 30%-chance toggle applied
    uniformly across the whole ostinato — variations were historically added
    cumulatively across repeats (Corelli's variation sets), so per-section
    change fits the form better than a track-wide coin flip.
    """
    notes = []
    scale = "harmonic_minor"
    seg = max(4, beats_per_bar * 4)

    char = _baroque_key_character(key_pc)
    mel_oct = char["mel_oct"]

    segs = prog_la_folia(key_pc, scale, steps, seg)
    if not segs:
        return notes

    toccata_bias = 40 if char["textures"][0] == "toccata" else 15
    tex_w = {"alberti": 100 - toccata_bias, "toccata": toccata_bias}

    sections = _plan_sections(len(segs), min_len=2, max_len=4)
    section_textures = []
    prev_tex = None
    for _s0, _len in sections:
        choices = [t for t in tex_w if t != prev_tex] or list(tex_w.keys())
        weights = [tex_w[t] for t in choices]
        tex = random.choices(choices, weights=weights, k=1)[0]
        section_textures.append(tex)
        prev_tex = tex

    for (start_idx, length), texture in zip(sections, section_textures):
        for seg_d in segs[start_idx:start_idx + length]:
            s0      = seg_d["s0"]
            root_pc = seg_d["root_pc"]
            qual    = seg_d["quality"]

            bass_oct = 2 + (1 if char["mel_oct"] == 4 and random.random() < 0.10 else 0)
            notes.append(mk(s0, note_name(root_pc, bass_oct), "4n",
                            0.63 + random.uniform(-0.05, 0.05), steps))

            if texture == "toccata":
                _bq_texture_toccata(notes, s0, seg, root_pc, qual, steps)
            else:
                _bq_texture_alberti(notes, s0, seg, root_pc, qual, steps)

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
