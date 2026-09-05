from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import shutil
import uuid

from melodies_generator import generate_loop as _ml_generate, STYLE_META

app = FastAPI()

# Directory to save loops
DATA_DIR = "data"
LOOPS_DIR = os.path.join(DATA_DIR, "loops")
GOLDEN_DIR = os.path.join(DATA_DIR, "golden_fond")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
INSTRUCTIONS_DIR = os.path.join(DATA_DIR, "instructions")
EXPORTS_DIR = os.path.join(DATA_DIR, "audio_exports")
os.makedirs(LOOPS_DIR, exist_ok=True)
os.makedirs(GOLDEN_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(INSTRUCTIONS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Prompts storage
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")

def load_prompts() -> list:
    if os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []

def save_prompts(data: list):
    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Diary storage
DIARY_FILE = os.path.join(DATA_DIR, "diary.json")

def load_diary() -> list:
    if os.path.exists(DIARY_FILE):
        try:
            with open(DIARY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []

def save_diary(data: list):
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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

# ─── Artists: какие лупы уже использованы каким исполнителем ────────────────
# data/artists.json: { "Artist": ["Loop name 1", "Loop name 2"], ... }
ARTISTS_FILE = os.path.join(DATA_DIR, "artists.json")

def load_artists() -> dict:
    if os.path.exists(ARTISTS_FILE):
        try:
            with open(ARTISTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_artists(data: dict):
    with open(ARTISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class ArtistMarkRequest(BaseModel):
    artist: str
    loops: List[str] = []
    used: bool  # true = пометить использованным, false = снять пометку

@app.get("/api/artists")
def get_artists():
    """{artist: [loop names]} — для селектора и бейджей 'used'."""
    return load_artists()

@app.post("/api/artists/mark")
def mark_artist_loops(req: ArtistMarkRequest):
    """Пометить/снять лупы как использованные исполнителем.
    Пустой loops создаёт исполнителя (пустая запись)."""
    artist = req.artist.strip()
    if not artist:
        raise HTTPException(status_code=400, detail="Empty artist name")
    data = load_artists()
    entry = data.setdefault(artist, [])
    changed = 0
    for name in req.loops:
        if req.used and name not in entry:
            entry.append(name)
            changed += 1
        elif not req.used and name in entry:
            entry.remove(name)
            changed += 1
    save_artists(data)
    return {"status": "success", "changed": changed}


class Note(BaseModel):
    step: int
    note: str
    duration: str
    velocity: Optional[float] = None
    chance: Optional[float] = None


# ── New Artists endpoints for Artists page ──────────────────────────────────
class ArtistCreateRequest(BaseModel):
    name: str

class ArtistRenameRequest(BaseModel):
    old_name: str
    new_name: str

class ArtistTracksRequest(BaseModel):
    artist: str
    tracks: List[str]

@app.post("/api/artists")
def create_artist(req: ArtistCreateRequest):
    """Создать нового исполнителя."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Empty artist name")
    data = load_artists()
    if name in data:
        raise HTTPException(status_code=400, detail="Artist already exists")
    data[name] = []
    save_artists(data)
    return {"status": "success", "artist": name}

@app.post("/api/artists/rename")
def rename_artist(req: ArtistRenameRequest):
    """Переименовать исполнителя."""
    old_name = req.old_name.strip()
    new_name = req.new_name.strip()
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Names cannot be empty")
    if old_name == new_name:
        raise HTTPException(status_code=400, detail="Names are identical")
    data = load_artists()
    if old_name not in data:
        raise HTTPException(status_code=404, detail="Artist not found")
    if new_name in data:
        raise HTTPException(status_code=400, detail="Artist with new name already exists")
    data[new_name] = data.pop(old_name)
    save_artists(data)
    return {"status": "success", "old_name": old_name, "new_name": new_name}

@app.delete("/api/artists/{name}")
def delete_artist(name: str):
    """Удалить исполнителя."""
    name = name.strip()
    data = load_artists()
    if name not in data:
        raise HTTPException(status_code=404, detail="Artist not found")
    del data[name]
    save_artists(data)
    return {"status": "success", "deleted": name}

@app.post("/api/artists/tracks")
def save_artist_tracks(req: ArtistTracksRequest):
    """Сохранить список треков для исполнителя."""
    artist = req.artist.strip()
    tracks = req.tracks
    data = load_artists()
    if artist not in data:
        raise HTTPException(status_code=404, detail="Artist not found")
    data[artist] = tracks
    save_artists(data)
    return {"status": "success", "artist": artist, "count": len(tracks)}

# ── Prompts ───────────────────────────────────────────────────────────────────
class PromptItem(BaseModel):
    songTitle: str = ""
    styles: str = ""
    negativePrompt: str = ""
    lyrics: str = ""

class PromptRecord(BaseModel):
    id: str
    name: str
    prompt: List[PromptItem] = []
    comment: str = ""
    artists: List[str] = []

@app.get("/api/prompts")
def get_prompts():
    return load_prompts()

@app.post("/api/prompts")
def create_prompt(rec: PromptRecord):
    name = (rec.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Prompt name required")
    data = load_prompts()
    if any(p["name"] == name for p in data):
        raise HTTPException(status_code=400, detail="Prompt name already exists")
    rec.id = rec.id or str(uuid.uuid4())
    data.append(rec.dict())
    save_prompts(data)
    return {"status": "success", "id": rec.id}

@app.put("/api/prompts/{pid}")
def update_prompt(pid: str, rec: PromptRecord):
    data = load_prompts()
    idx = next((i for i, p in enumerate(data) if p["id"] == pid), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if any(p["name"] == rec.name and p["id"] != pid for p in data):
        raise HTTPException(status_code=400, detail="Prompt name already exists")
    rec.id = pid
    data[idx] = rec.dict()
    save_prompts(data)
    return {"status": "success", "id": pid}

@app.delete("/api/prompts/{pid}")
def delete_prompt(pid: str):
    data = load_prompts()
    nxt = [p for p in data if p["id"] != pid]
    if len(nxt) == len(data):
        raise HTTPException(status_code=404, detail="Prompt not found")
    save_prompts(nxt)
    return {"status": "success", "deleted": pid}

# ── Diary ─────────────────────────────────────────────────────────────────────
class DiaryEntry(BaseModel):
    id: str
    date: str  # ISO YYYY-MM-DD
    title: str
    body: str = ""
    tags: List[str] = []
    artists: List[str] = []
    prompts: List[str] = []  # prompt ids
    status: str = "open"  # open | done

@app.get("/api/diary")
def get_diary():
    return load_diary()

@app.post("/api/diary")
def create_diary(entry: DiaryEntry):
    if not entry.title.strip():
        raise HTTPException(status_code=400, detail="Title required")
    data = load_diary()
    entry.id = entry.id or str(uuid.uuid4())
    if any(d["id"] == entry.id for d in data):
        raise HTTPException(status_code=400, detail="Duplicate id")
    data.append(entry.dict())
    save_diary(data)
    return {"status": "success", "id": entry.id}

@app.put("/api/diary/{did}")
def update_diary(did: str, entry: DiaryEntry):
    data = load_diary()
    idx = next((i for i, d in enumerate(data) if d["id"] == did), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.id = did
    data[idx] = entry.dict()
    save_diary(data)
    return {"status": "success", "id": did}

@app.delete("/api/diary/{did}")
def delete_diary(did: str):
    data = load_diary()
    nxt = [d for d in data if d["id"] != did]
    if len(nxt) == len(data):
        raise HTTPException(status_code=404, detail="Entry not found")
    save_diary(nxt)
    return {"status": "success", "deleted": did}
    step: int
    note: str
    duration: str
    velocity: Optional[float] = None
    chance: Optional[float] = None

class Loop(BaseModel):
    name: str
    bpm: int
    instrument: str
    steps: int
    key: Optional[str] = None
    scale: Optional[str] = None
    swing: Optional[float] = 0.0
    notes: List[Note]
    comment: Optional[str] = None  # free-form user text (loop info)
    style: Optional[str] = None    # display style label (empty = hide in row)

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

@app.get("/api/archive")
def get_archive(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    loops = []
    for filename in os.listdir(ARCHIVE_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(ARCHIVE_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["_filename"] = filename
                    data["_archive"] = True
                    loops.append(data)
            except Exception:
                pass
    return loops

@app.post("/api/archive/{filename}/send")
def send_to_archive(filename: str):
    """Отправить трек из Golden Fund в архив (файл переезжает)."""
    safe = os.path.basename(filename)
    src = os.path.join(GOLDEN_DIR, safe)
    dst = os.path.join(ARCHIVE_DIR, safe)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail="Track not found in Golden")
    if os.path.exists(dst):
        raise HTTPException(status_code=400, detail="Already in archive")
    shutil.move(src, dst)
    return {"status": "ok", "archived": safe}

@app.post("/api/archive/{filename}/restore")
def restore_from_archive(filename: str):
    """Вернуть трек из архива обратно в Golden Fund."""
    safe = os.path.basename(filename)
    src = os.path.join(ARCHIVE_DIR, safe)
    dst = os.path.join(GOLDEN_DIR, safe)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail="Track not found in archive")
    if os.path.exists(dst):
        raise HTTPException(status_code=400, detail="Track with same filename already in Golden")
    shutil.move(src, dst)
    return {"status": "ok", "restored": safe}

@app.post("/api/golden/{filename}/copy")
def copy_golden_to_loops(filename: str, response: Response):
    """Copy a golden loop into the shared loops catalog (golden copy stays)."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    safe = os.path.basename(filename)
    src = os.path.join(GOLDEN_DIR, safe)
    if not os.path.isfile(src):
        raise HTTPException(status_code=404, detail="Golden loop not found")
    base, ext = os.path.splitext(safe)
    dest = os.path.join(LOOPS_DIR, safe)
    counter = 1
    while os.path.exists(dest):
        counter += 1
        dest = os.path.join(LOOPS_DIR, f"{base}_{counter}{ext}")
    shutil.copy2(src, dest)
    return {"ok": True, "filename": os.path.basename(dest)}

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
        
    # Проверка уникальности имени в ОБОИХ каталогах
    existing_names = _get_existing_names()
    base_name = safe_name.replace(' ', '_').lower()
    filename = f"{base_name}.json"
    filepath = os.path.join(LOOPS_DIR, filename)
    
    # Проверка уникальности имени (по display name)
    if loop.name in _get_existing_names():
        raise HTTPException(status_code=400, detail=f"Track with name '{loop.name}' already exists")
    
    # Файл: проверка коллизий имени файла
    filepath = os.path.join(LOOPS_DIR, filename)
    counter = 1
    while os.path.exists(filepath):
        counter += 1
        filename = f"{base_name}_{counter}.json"
        filepath = os.path.join(LOOPS_DIR, filename)
        
    data = loop.dict()
    if data.get("comment") is None:
        data["comment"] = ""

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return {"status": "success", "filename": filename}


def _get_existing_names():
    """Возвращает множество всех имён треков (без расширения) в обоих каталогах."""
    names = set()
    for search_dir in [LOOPS_DIR, GOLDEN_DIR, ARCHIVE_DIR]:
        for f in os.listdir(search_dir):
            if f.endswith(".json") and f != os.path.basename(META_FILE):
                try:
                    with open(os.path.join(search_dir, f), "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                        if "name" in data:
                            names.add(data["name"])
                except Exception:
                    pass
    return names


def _update_artists_on_rename(old_name: str, new_name: str):
    """Обновляет artists.json при переименовании трека."""
    try:
        artists = load_artists()
        changed = False
        for artist, tracks in artists.items():
            if old_name in tracks:
                idx = tracks.index(old_name)
                tracks[idx] = new_name
                changed = True
        if changed:
            save_artists(artists)
    except Exception:
        pass


@app.put("/api/loops/{filename}")
def update_loop(filename: str, loop: Loop):
    safe_filename = os.path.basename(filename)
    if safe_filename == os.path.basename(META_FILE):
        raise HTTPException(status_code=400, detail="Reserved filename")
        
    filepath = None
    for search_dir in [LOOPS_DIR, GOLDEN_DIR, ARCHIVE_DIR]:
        candidate = os.path.join(search_dir, safe_filename)
        if os.path.exists(candidate):
            filepath = candidate
            break
            
    if not filepath:
        raise HTTPException(status_code=404, detail="Loop not found")

    data = loop.dict()
    if data.get("comment") is None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data["comment"] = json.load(f).get("comment", "")
        except Exception:
            data["comment"] = ""

    # Проверка уникальности нового имени
    new_name = data.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Empty track name")
    
    existing_names = _get_existing_names()
    # Исключаем текущий трек из проверки (он будет переименован)
    old_name = None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            old_name = json.load(f).get("name", "")
    except Exception:
        pass
    existing_names.discard(old_name)
    
    if new_name in existing_names:
        raise HTTPException(status_code=400, detail=f"Track with name '{new_name}' already exists")

    # Обновляем данные
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    
    # Если имя изменилось — обновляем artists.json и, при необходимости, переименовываем файл
    if new_name != old_name:
        _update_artists_on_rename(old_name, new_name)
        # Переименование файла (если нужно, чтобы filename соответствовал name)
        new_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', new_name).lower() + ".json"
        new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
        if not os.path.exists(new_filepath) and new_filename != safe_filename:
            os.rename(filepath, new_filepath)
            safe_filename = new_filename

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

class BulkCommentRequest(BaseModel):
    tracks: List[str]   # loop names, one per entry
    comment: str        # text appended to each matched loop

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
        
    # Проверка уникальности display name в обоих каталогах
    if loop["name"] in _get_existing_names():
        raise HTTPException(status_code=400, detail=f"Track with name '{loop['name']}' already exists")
    
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

    for search_dir in [LOOPS_DIR, GOLDEN_DIR, ARCHIVE_DIR]:
        filepath = os.path.join(search_dir, safe_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            # Keep metadata if the same-named file still exists in the other
            # directory (e.g. a catalog copy of a golden loop): deleting the
            # copy must not wipe the golden original's rating/stars.
            other_dirs = [d for d in (LOOPS_DIR, GOLDEN_DIR) if d != search_dir]
            still_exists = any(os.path.exists(os.path.join(d, safe_filename)) for d in other_dirs)
            if not still_exists:
                meta = load_meta()
                if safe_filename in meta:
                    del meta[safe_filename]
                    save_meta(meta)
            return {"status": "success"}
    raise HTTPException(status_code=404, detail="File not found")

@app.delete("/api/clear/loops")
def clear_loops():
    """Delete all audio files from the Downloads\\AIMusicTools\\Loops folder."""
    downloads_dir = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Downloads', 'AIMusicTools', 'Loops')
    count = 0
    if os.path.exists(downloads_dir):
        for f in os.listdir(downloads_dir):
            if f.endswith((".webm", ".wav", ".mp3")):
                os.remove(os.path.join(downloads_dir, f))
                count += 1
    return {"status": "ok", "deleted": count}

@app.delete("/api/clear/exports")
def clear_exports():
    """Delete all audio files from the exports directory."""
    count = 0
    for f in os.listdir(EXPORTS_DIR):
        if f.endswith((".webm", ".wav", ".mp3")):
            os.remove(os.path.join(EXPORTS_DIR, f))
            count += 1
    return {"status": "ok", "deleted": count}

@app.delete("/api/clear/catalog")
def clear_catalog():
    """Delete all JSON files from loops only (golden_fond is preserved)."""
    count = 0
    for f in os.listdir(LOOPS_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(LOOPS_DIR, f))
            count += 1
    return {"status": "ok", "deleted": count}

@app.post("/api/bulk_comment")
def bulk_comment(req: BulkCommentRequest):
    """Append comment text to every loop (catalog + golden) matching the given names.

    New text is appended AFTER a blank line at the end of the existing comment.
    """
    names = [t.strip() for t in req.tracks if t.strip()]
    wanted = {}                      # lower -> original (dedupe, keep first spelling)
    for n in names:
        wanted.setdefault(n.lower(), n)
    total = len(names)
    updated_keys = set()

    meta_filename = os.path.basename(META_FILE)
    for search_dir in [LOOPS_DIR, GOLDEN_DIR, ARCHIVE_DIR]:
        for f in os.listdir(search_dir):
            if not f.endswith(".json") or f == meta_filename:
                continue
            filepath = os.path.join(search_dir, f)
            try:
                with open(filepath, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
            except Exception:
                continue
            key = str(data.get("name", "")).strip().lower()
            if key not in wanted:
                continue
            old = str(data.get("comment") or "").rstrip()
            new_text = req.comment.strip()
            data["comment"] = f"{old}\n\n{new_text}" if old else new_text
            try:
                with open(filepath, "w", encoding="utf-8") as jf:
                    json.dump(data, jf, indent=4, ensure_ascii=False)
                updated_keys.add(key)   # same name in loops/ and golden/ counts once
            except Exception:
                pass

    not_found = [orig for low, orig in wanted.items() if low not in updated_keys]
    return {
        "status": "ok",
        "requested": total,
        "updated": len(updated_keys),
        "not_found": not_found,
    }

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
    # Path to Windows Downloads folder (AIMusicTools\\Loops)
    downloads_dir = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Downloads', 'AIMusicTools', 'Loops')
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

@app.post("/api/exports/trim/{filename}")
async def trim_export_audio(filename: str, request: Request):
    """Saves trimmed audio, overwriting the original file."""
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(EXPORTS_DIR, safe_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    data = await request.body()
    # Save trimmed version (overwrite original for simplicity)
    with open(filepath, "wb") as f:
        f.write(data)
    return {"status": "ok", "filename": safe_filename}

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
    if not safe_new.endswith((".webm", ".wav", ".mp3")):
        safe_new += ".wav"
        
    old_path = os.path.join(EXPORTS_DIR, safe_filename)
    new_path = os.path.join(EXPORTS_DIR, safe_new)
    
    if not os.path.exists(old_path):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="New filename already exists")
        
    os.rename(old_path, new_path)
    
    # Update corresponding JSON file in loops or golden_fond so we don't break Regeneration
    old_base = os.path.splitext(safe_filename)[0]
    new_base = os.path.splitext(safe_new)[0]
    
    import json
    import re
    
    for search_dir in [LOOPS_DIR, GOLDEN_DIR, ARCHIVE_DIR]:
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
