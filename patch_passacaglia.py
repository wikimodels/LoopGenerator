import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('melodies_generator.py', encoding='utf-8') as f:
    content = f.read()

# ── Step 1: add anchor_octave param ──────────────────────────────────────
OLD1 = 'def _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps):'
NEW1 = 'def _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps, anchor_octave=3):'
if OLD1 in content:
    content = content.replace(OLD1, NEW1, 1)
    print('Step 1a OK: signature updated')
else:
    print('Step 1a FAIL'); sys.exit(1)

OLD1b = '    pad_pitches = voice_lead(intervals, root_pc, prev_pad, anchor_octave=3, max_octave=4)'
NEW1b = '    pad_pitches = voice_lead(intervals, root_pc, prev_pad, anchor_octave=anchor_octave, max_octave=anchor_octave + 1)'
if OLD1b in content:
    content = content.replace(OLD1b, NEW1b, 1)
    print('Step 1b OK: body updated')
else:
    print('Step 1b FAIL'); sys.exit(1)

# ── Step 2: find and update the call inside gen_baroque_passacaglia ───────
# The comment has Unicode box-drawing chars; find by the function call line only
CALL_LINE = '        prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps)'
NEW_CALL  = '        prev_pad = _bq_texture_block_chord(notes, s0, root_pc, qual, prev_pad, steps, anchor_octave=4)'

# There may be multiple calls in the file (baroque, pachelbel, etc.)
# We only want the one inside gen_baroque_passacaglia.
# Find gen_baroque_passacaglia first, then patch the FIRST occurrence after it.
marker = 'def gen_baroque_passacaglia('
mp = content.find(marker)
if mp < 0:
    print('Step 2 FAIL: gen_baroque_passacaglia not found'); sys.exit(1)

# Only search after the function definition
after = content[mp:]
if CALL_LINE in after:
    patched_after = after.replace(CALL_LINE, NEW_CALL, 1)
    content = content[:mp] + patched_after
    print('Step 2 OK: passacaglia call now uses anchor_octave=4')
else:
    print('Step 2 FAIL: call line not found after function start')
    idx = after.find('_bq_texture_block_chord')
    print(repr(after[max(0,idx-80):idx+100]))
    sys.exit(1)

with open('melodies_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('File written OK')
