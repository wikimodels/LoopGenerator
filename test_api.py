import urllib.request
import json

data = json.dumps({"style":"video_game", "key":"C", "beats_per_bar":4}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:8000/api/generate", data=data, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req) as f:
        res = json.loads(f.read().decode("utf-8"))
        print("Success:", res.get("filename"))
except Exception as e:
    print("Error:", e)
    if hasattr(e, "read"):
        print(e.read().decode("utf-8"))
