import json

with open("test_bossa.json") as f:
    data = json.load(f)

for note in sorted(data["notes"], key=lambda n: n["step"]):
    if "duration" in note and note["duration"] == "8n":
        print(f"Step {note['step']:>2} : {note['note']} ({note['velocity']})")
