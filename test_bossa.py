import json
from melodies_generator import generate_loop

try:
    res = generate_loop("bossa_nova", "C", steps=64)
    print(f"Bossa Nova generated: {len(res['notes'])} notes")
    with open("test_bossa.json", "w") as f: json.dump(res, f)
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
