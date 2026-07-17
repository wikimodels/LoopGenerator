from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import uuid

from melodies_generator import generate_loop as _ml_generate, STYLE_META

app = FastAPI()

# Directory to save loops
DATA_DIR = "data"
LOOPS_DIR = os.path.join(DATA_DIR, "loops")
GOLDEN_DIR = os.path.join(DATA_DIR, "golden_fond")
INSTRUCTIONS_DIR = os.path.join(DATA_DIR, "instructions")
EXPORTS_DIR = os.path.join(DATA_DIR, "audio_exports")
os.makedirs(LOOPS_DIR, exist_ok=True)
os.makedirs(GOLDEN_DIR, exist_ok=True)
os.makedirs(INSTRUCTIONS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Metadata file (ratings, notes, etc.)
META_FILE = os.path.join(DATA_DIR, "_loop_meta.json")

def load_meta() -> dict:
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_meta(meta: dict):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

class Note(BaseModel):
    step: int
    note: str
    duration: str

class Loop(BaseModel):
    name: str
    bpm: int
    instrument: str
    steps: int
    notes: List[Note]

class LoopMeta(BaseModel):
    rating: Optional[int] = 0      # 0-5 stars
    tags: Optional[List[str]] = []
    notes: Optional[str] = ""

@app.get("/api/loops")
def get_loops(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    loops = []
    meta_filename = os.path.basename(META_FILE)
    for filename in os.listdir(LOOPS_DIR):
        if filename.endswith(".json") and filename != meta_filename:
            filepath = os.path.join(LOOPS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["_filename"] = filename
                    loops.append(data)
            except Exception:
                pass
    return loops

@app.get("/api/instructions")
def get_instructions():
    instructions = []
    if os.path.exists(INSTRUCTIONS_DIR):
        for filename in os.listdir(INSTRUCTIONS_DIR):
            if filename.endswith(".md"):
                filepath = os.path.join(INSTRUCTIONS_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        style_name = filename[:-3].capitalize()
                        instructions.append({
                            "name": style_name,
                            "content": content
                        })
                except Exception:
                    pass
    return instructions


@app.get("/api/golden")
def get_golden(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    loops = []
    for filename in os.listdir(GOLDEN_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(GOLDEN_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["_filename"] = filename
                    data["_golden"] = True
                    loops.append(data)
            except Exception:
                pass
    return loops

@app.post("/api/loops")
def save_loop(loop: Loop):
    # simple sanitization
    safe_name = "".join([c for c in loop.name if c.isalnum() or c in (' ', '-', '_')]).rstrip()
    if not safe_name:
        import uuid
        safe_name = f"loop_{uuid.uuid4().hex[:8]}"
        
    filename = f"{safe_name.replace(' ', '_').lower()}.json"
    
    if filename == os.path.basename(META_FILE):
        raise HTTPException(status_code=400, detail="Reserved filename")
        
    base_name = safe_name.replace(' ', '_').lower()
    filepath = os.path.join(LOOPS_DIR, filename)
    counter = 1
    while os.path.exists(filepath):
        counter += 1
        filename = f"{base_name}_{counter}.json"
        filepath = os.path.join(LOOPS_DIR, filename)
        
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(loop.dict(), f, indent=4)
    return {"status": "success", "filename": filename}


@app.put("/api/loops/{filename}")
def update_loop(filename: str, loop: Loop):
    safe_filename = os.path.basename(filename)
    if safe_filename == os.path.basename(META_FILE):
        raise HTTPException(status_code=400, detail="Reserved filename")
        
    filepath = None
    for search_dir in [LOOPS_DIR, GOLDEN_DIR]:
        candidate = os.path.join(search_dir, safe_filename)
        if os.path.exists(candidate):
            filepath = candidate
            break
            
    if not filepath:
        raise HTTPException(status_code=404, detail="Loop not found")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(loop.dict(), f, indent=4)
    return {"status": "success", "filename": safe_filename}



# -----------------------------------------------------------------
# STYLE-BASED GENERATION via melodies_generator
# -----------------------------------------------------------------
VALID_KEYS = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

class GenerateRequest(BaseModel):
    style: str
    key: str
    bpm: int = 100
    steps: int = 64
    beats_per_bar: int = 4
    seed: Optional[int] = None
    name: Optional[str] = None
    is_batch: bool = False

class RenameRequest(BaseModel):
    new_filename: str

class DownloadRequest(BaseModel):
    filenames: list[str]

@app.get("/api/styles")
def get_styles():
    """Return list of available generation styles."""
    return list(STYLE_META.keys())

@app.post("/api/generate")
def generate_loop_endpoint(req: GenerateRequest):
    """Generate a loop with melodies_generator and save it to the loops directory."""
    if req.style not in STYLE_META:
        raise HTTPException(status_code=400, detail=f"Unknown style '{req.style}'")
    if req.key not in VALID_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid key '{req.key}'")
    if not (40 <= req.bpm <= 240):
        raise HTTPException(status_code=400, detail="BPM must be 40–240")

    try:
        loop = _ml_generate(
            req.style, req.key,
            name=req.name if req.name and req.name.strip() else None,
            bpm=req.bpm,
            steps=req.steps,
            beats_per_bar=req.beats_per_bar,
            seed=req.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Persist to disk
    if req.is_batch:
        # Build a smart, non-redundant name
        style_parts = req.style.split('_')
        scale_parts = loop["scale"].lower().replace('-', ' ').replace('_', ' ').split()
        
        words = []
        for p in style_parts:
            words.append(p.title())
            
        for p in scale_parts:
            pt = p.title()
            # Add scale parts only if they aren't already in the style name
            if pt not in words:
                words.append(pt)
                
        # Key
        words.append(req.key)
        # Seed
        seed_str = str(req.seed) if req.seed is not None else "Rand"
        words.append(seed_str)
        
        loop["name"] = " ".join(words)
        
        # For filename, lower case and use underscores, replace # with sharp
        safe_key = req.key.replace('#', 'sharp').lower()
        fn_words = [w.lower() if w != req.key else safe_key for w in words]
        base = "_".join(fn_words)
    else:
        safe = "".join(c for c in loop["name"] if c.isalnum() or c in " -_").strip()
        base = safe.replace(" ", "_").lower() or f"loop_{uuid.uuid4().hex[:8]}"
        
    filename = f"{base}.json"
    filepath = os.path.join(LOOPS_DIR, filename)
    ctr = 1
    while os.path.exists(filepath):
        ctr += 1
        filename = f"{base}_{ctr}.json"
        filepath = os.path.join(LOOPS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(loop, f, indent=4, ensure_ascii=False)

    return {"status": "success", "filename": filename, "loop": loop}

@app.delete("/api/loops/{filename}")
def delete_loop(filename: str):
    # secure delete — search in both loops/ and golden_fond/
    safe_filename = os.path.basename(filename)
    if safe_filename == os.path.basename(META_FILE):
        raise HTTPException(status_code=400, detail="Cannot delete metadata file")

    for search_dir in [LOOPS_DIR, GOLDEN_DIR]:
        filepath = os.path.join(search_dir, safe_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            meta = load_meta()
            if safe_filename in meta:
                del meta[safe_filename]
                save_meta(meta)
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/meta")
def get_meta():
    return load_meta()

@app.patch("/api/meta/{filename}")
def update_meta(filename: str, patch: LoopMeta):
    safe_filename = os.path.basename(filename)
    meta = load_meta()
    existing = meta.get(safe_filename, {})
    old_rating = existing.get("rating", 0)
    incoming = patch.dict(exclude_none=True)
    existing.update(incoming)
    new_rating = existing.get("rating", 0)
    meta[safe_filename] = existing
    save_meta(meta)

    # Move file between loops/ and golden_fond/ based on rating
    loops_path  = os.path.join(LOOPS_DIR,  safe_filename)
    golden_path = os.path.join(GOLDEN_DIR, safe_filename)

    if new_rating == 5 and old_rating != 5:
        # Promote to golden
        if os.path.exists(loops_path):
            import shutil
            shutil.move(loops_path, golden_path)
    elif new_rating != 5 and old_rating == 5:
        # Demote from golden back to loops
        if os.path.exists(golden_path):
            import shutil
            shutil.move(golden_path, loops_path)

    return {"status": "success", "filename": safe_filename, "meta": existing, "rating": new_rating}

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)
# Serve the static files
@app.post("/api/export_audio/local_download")
def local_download_exports(req: DownloadRequest):
    import shutil
    # Path to Windows Downloads folder
    downloads_dir = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Downloads', 'Loops')
    os.makedirs(downloads_dir, exist_ok=True)
    
    downloaded = []
    for filename in req.filenames:
        safe_filename = os.path.basename(filename)
        src = os.path.join(EXPORTS_DIR, safe_filename)
        if os.path.exists(src):
            dst = os.path.join(downloads_dir, safe_filename)
            shutil.copy2(src, dst)
            downloaded.append(safe_filename)
            
    return {"status": "ok", "downloaded": downloaded, "destination": downloads_dir}

@app.post("/api/export_audio/{filename}")
async def upload_audio(filename: str, request: Request):
    """Saves exported audio (blob) to the exports directory."""
    data = await request.body()
    filepath = os.path.join(EXPORTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    return {"status": "ok", "filename": filename}

@app.get("/api/exports")
def list_exports():
    """Lists all exported audio files."""
    files = []
    for f in os.listdir(EXPORTS_DIR):
        if f.endswith(".webm") or f.endswith(".wav") or f.endswith(".mp3"):
            filepath = os.path.join(EXPORTS_DIR, f)
            stat = os.stat(filepath)
            files.append({
                "filename": f,
                "size": stat.st_size,
                "created_at": stat.st_ctime
            })
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files

@app.delete("/api/export_audio/{filename}")
def delete_export_audio(filename: str):
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(EXPORTS_DIR, safe_filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return {"status": "ok", "filename": safe_filename}
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/api/export_audio/{filename}/rename")
def rename_export_audio(filename: str, req: RenameRequest):
    safe_filename = os.path.basename(filename)
    safe_new = os.path.basename(req.new_filename)
    if not safe_new.endswith(".webm"):
        safe_new += ".webm"
        
    old_path = os.path.join(EXPORTS_DIR, safe_filename)
    new_path = os.path.join(EXPORTS_DIR, safe_new)
    
    if not os.path.exists(old_path):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="New filename already exists")
        
    os.rename(old_path, new_path)
    
    # Update corresponding JSON file in loops or golden_fond so we don't break Regeneration
    old_base = safe_filename[:-5] # remove .webm
    new_base = safe_new[:-5]
    
    import json
    import re
    
    for search_dir in [LOOPS_DIR, GOLDEN_DIR]:
        for f in os.listdir(search_dir):
            if f.endswith(".json"):
                fp = os.path.join(search_dir, f)
                try:
                    with open(fp, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                    
                    # Match name using the exact same logic as the frontend cleanName
                    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', data.get("name", "loop"))
                    if clean_name == old_base:
                        # Found the matching JSON. Update name and rename file.
                        data["name"] = new_base
                        
                        new_json_name = new_base.replace(' ', '_').lower() + ".json"
                        new_fp = os.path.join(search_dir, new_json_name)
                        
                        with open(fp, "w", encoding="utf-8") as jf:
                            json.dump(data, jf, indent=4)
                            
                        if fp != new_fp and not os.path.exists(new_fp):
                            os.rename(fp, new_fp)
                        break
                except Exception:
                    pass

    return {"status": "ok", "new_filename": safe_new}
app.mount("/exports", StaticFiles(directory=EXPORTS_DIR), name="exports")
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
