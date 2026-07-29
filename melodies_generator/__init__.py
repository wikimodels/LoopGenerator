import random
import math
from .core import *
from .baroque import *
from .renaissance import *
from .jazz import *
from .classical import *
from .minimalism import *
from .contemporary import *
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

