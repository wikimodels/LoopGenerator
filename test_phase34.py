import json
from melodies_generator import generate_loop

try:
    res = generate_loop("lofi", "C", steps=64)
    print(f"Lo-Fi generated: {len(res['notes'])} notes")
    with open("test_lofi.json", "w") as f: json.dump(res, f)
    
    res2 = generate_loop("neo_soul", "C", steps=64)
    print(f"Neo-Soul generated: {len(res2['notes'])} notes")
    with open("test_neosoul.json", "w") as f: json.dump(res2, f)
    
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
