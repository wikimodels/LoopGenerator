import urllib.request
import json

req = urllib.request.Request("http://127.0.0.1:8000/api/styles")
try:
    with urllib.request.urlopen(req) as f:
        res = json.loads(f.read().decode("utf-8"))
        print("Styles:", res)
except Exception as e:
    print("Error:", e)
    if hasattr(e, "read"):
        print(e.read().decode("utf-8"))
