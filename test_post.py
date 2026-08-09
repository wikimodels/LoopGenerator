import urllib.request
import json

with open("test_payload.json", "r", encoding="utf-8") as f:
    data = json.load(f)

req = urllib.request.Request("http://127.0.0.1:8000/api/loops", data=json.dumps(data[0]).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as res:
        print("Status Code:", res.getcode())
        print("Response:", res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError Status Code:", e.code)
    print("HTTPError Response:", e.read().decode('utf-8'))
