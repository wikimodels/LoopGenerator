import json
from melodies_generator import generate_loop

try:
    res = generate_loop("video_game", "C", steps=48, beats_per_bar=3)
    print(f"Video Game 3/4: {len(res['notes'])} notes")
    
    res = generate_loop("video_game", "C", steps=80, beats_per_bar=5)
    print(f"Video Game 5/4: {len(res['notes'])} notes")
    
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
