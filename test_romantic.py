import json
from melodies_generator import generate_loop

try:
    res = generate_loop("romantic", "C", steps=64)
    print(f"Romantic generated: {len(res['notes'])} notes")
    with open("test_romantic.json", "w") as f: json.dump(res, f)
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
