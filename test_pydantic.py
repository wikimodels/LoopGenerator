import json
from main import Loop

data_str = """
[
  {
    "name": "Renaissance Lute Ground Dance",
    "bpm": 108,
    "instrument": "piano",
    "steps": 64,
    "key": "D",
    "scale": "Dorian",
    "swing": 0.05,
    "notes": [
      { "step": 0, "note": "D3", "duration": "8n", "velocity": 0.95 },
      { "step": 0, "note": "D4", "duration": "16n", "velocity": 0.85 },
      { "step": 28, "note": "C#5", "duration": "8n", "velocity": 0.85 }
    ]
  }
]
"""

data = json.loads(data_str)
try:
    for loop in data:
        Loop(**loop)
    print("OK")
except Exception as e:
    print("ERROR:", e)
