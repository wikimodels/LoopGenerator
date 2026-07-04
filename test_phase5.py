import json
from melodies_generator import generate_loop

try:
    res = generate_loop("video_game", "C", steps=64)
    print(f"Video Game generated: {len(res['notes'])} notes")
    with open("test_videogame.json", "w") as f: json.dump(res, f)
    
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
