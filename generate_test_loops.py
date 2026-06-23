import json
import random
import os

data_dir = r"d:\GitHub\LoopGenerator\data"

for i in range(1, 101):
    loop = {
        "name": f"Test Loop {i:03d}",
        "bpm": random.randint(80, 160),
        "instrument": random.choice(["piano", "synth", "amSynth", "fmSynth", "drums"]),
        "steps": random.choice([16, 32]),
        "key": random.choice(["C", "D", "E", "F", "G", "A", "B"]),
        "scale": random.choice(["Major", "Minor", "Pentatonic"]),
        "swing": round(random.uniform(0.0, 0.7), 2),
        "notes": []
    }
    
    with open(os.path.join(data_dir, f"test_loop_{i:03d}.json"), "w", encoding="utf-8") as f:
        json.dump(loop, f, indent=4)
        
print("100 loops generated.")
