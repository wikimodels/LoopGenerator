#!/usr/bin/env python3
"""
Бот стандартизации Renaissance треков.
Приводит name/style к формату:
  name:  Renaissance [Подвид] - [Описание]
  style: Renaissance [Подвид] [Лад]

Подвид и лад извлекаются из имеющихся name/style/notes.
"""
import json
import re
from pathlib import Path

LOOPS_DIR = Path(r"D:\GitHub\LoopGenerator\data\loops")

# Известные подвиды Renaissance (порядок важен — длинные первыми)
SUBTYPES = [
    "Passamezzo Antico",
    "Sacred Chorale",
    "Basse Danse",
    "Folia",
    "Passamezzo",
    "Ricercar",
    "Canzona",
    "Lamento",
    "Madrigal",
    "Tiento",
    "Romanesca",
    "Pavane",
    "Tourdion",
    "Chanson",
    "Chorale",
    "Sarabande",
    "Hymn",
    "Choral",
    "Chorale",
    "Saltarello",
    "Basse",
    "Sacred",
]

# Лады / тональности
MODES = [
    "Dorian", "Phrygian", "Aeolian", "Lydian", "Mixolydian",
    "Ionian", "Locrian", "Minor", "Major",
]

# Дефолтные лады для подвидов (когда в данных нет явного)
DEFAULT_MODE_FOR_SUBTYPE = {
    "Pavane": "Dorian",
    "Folia": "Dorian",
    "Passamezzo": "Dorian",
    "Passamezzo Antico": "Dorian",
    "Basse Danse": "Dorian",
    "Tourdion": "Dorian",
    "Lamento": "Aeolian",
    "Madrigal": "Aeolian",
    "Romanesca": "Aeolian",
    "Ricercar": "Dorian",
    "Canzona": "Dorian",
    "Tiento": "Phrygian",
    "Chanson": "Ionian",
    "Hymn": "Dorian",
    "Choral": "Dorian",
    "Saltarello": "Dorian",
    "Sarabande": "Minor",
}

# Маппинг не-Renaissance названий → Renaissance подвид
NON_REN_TO_SUBTYPE = {
    "Byzantine": "Choral",
    "Gothic": "Ricercar",  # Gothic Organ etc -> Ricercar as default
    "Cathedral": "Chorale",
    "Grand Hymn": "Hymn",
    "Harmonic Ricercar": "Ricercar",
    "Lacrimosa": "Lamento",
    "Lively": "Basse Danse",
    "Majestic Sarabande": "Sarabande",
    "Melodic Ricercar": "Ricercar",
    "Ornamented Chanson": "Chanson",
    "Requiem Canticle": "Chorale",
    "Sacred Passacaglia": "Passacaglia",
    "Solemn Chaconne": "Chaconne",
    "Stately Pavane": "Pavane",
    "The Clockwork Cathedral1": "Ricercar",
    "Winter Nocturne": "Lamento",
    "Cantabile Ricercar": "Ricercar",
    "Harmonic Ricercar": "Ricercar",
    "Byzantine Choral": "Choral",
    "Expressive Madrigal": "Madrigal",
    "Cathedral Elegy": "Chorale",
    "Cathedral Passacaglia": "Passacaglia",
    "Gothic Arpeggiated Ostinato": "Ricercar",
    "Gothic Cathedral": "Chorale",
    "Gothic Organ": "Ricercar",
    "Requiem Canticle": "Chorale",
    "Sacred Passacaglia": "Passacaglia",
    "Solemn Chaconne": "Chaconne",
    "Stately Pavane": "Pavane",
    "Cantabile": "Ricercar",
}


def extract_subtype(text: str) -> str | None:
    """Ищет подвид в тексте (case-insensitive, длинные первыми)."""
    if not text:
        return None
    low = text.lower()
    for sub in SUBTYPES:
        if sub.lower() in low:
            return sub
    return None


def extract_mode(text: str) -> str | None:
    """Ищет лад в тексте."""
    if not text:
        return None
    # Ищем целые слова
    for mode in MODES:
        if re.search(rf"\b{re.escape(mode)}\b", text, re.IGNORECASE):
            # Нормализуем регистр: первая заглавная
            return mode if mode in ("Major", "Minor") else mode
    return None


def extract_description(name: str, subtype: str) -> str:
    """Вытаскивает описание после ' - ' или после подтипа."""
    # Если есть " - ", берём всё после него
    if " - " in name:
        parts = name.split(" - ", 1)
        desc = parts[1].strip()
        # Убрать упоминание подтипа/лада из описания если дублируется
        return desc
    # Иначе убираем Renaissance/подтип и берём остаток
    # Например "Gothic Arpeggiated Ostinato" -> "Arpeggiated Ostinato"
    # Для Renaissance "Renaissance Folia - X" уже обработано выше
    # Для остальных — отрезаем подтип
    if subtype and subtype.lower() in name.lower():
        # Найти позицию подтипа и взять после него
        idx = name.lower().find(subtype.lower())
        after = name[idx + len(subtype):].strip(" -:–—")
        if after:
            return after
    # Fallback: всё после первого слова
    return name.strip()


def determine_mode_for_track(data: dict, subtype: str) -> str:
    """Определяет лад: из name/style/scale/key/notes."""
    # 1. Прямо из name/style
    for field in ("style", "name"):
        mode = extract_mode(data.get(field, ""))
        if mode:
            return mode
    # 2. Из поля scale
    scale = data.get("scale")
    if scale:
        # scale может быть "Dorian", "Minor" etc
        for mode in MODES:
            if mode.lower() == scale.lower():
                return mode
        # "natural_minor" -> Minor
        if "minor" in scale.lower():
            return "Minor"
        if "major" in scale.lower():
            return "Major"
    # 3. Из нот - анализ гаммы (упрощенно: смотрим на используемые pitch classes)
    notes = data.get("notes", [])
    if notes:
        pcs = set()
        for n in notes:
            note_str = n.get("note", "")
            # Извлекаем pitch class: C, C#, D etc
            m = re.match(r"([A-G]#?b?)", note_str)
            if m:
                pcs.add(m.group(1))
        # Эвристика: если много хроматики -> Minor
        # Если есть F# и C# -> Lydian/Dorian etc. Упрощаем.
        pass
    # 4. Дефолт по подтипу
    if subtype in DEFAULT_MODE_FOR_SUBTYPE:
        return DEFAULT_MODE_FOR_SUBTYPE[subtype]
    return "Dorian"  # общий дефолт для Renaissance


def standardize_file(path: Path) -> dict:
    """Читает, стандартизует, перезаписывает. Возвращает отчёт."""
    # Читаем с обработкой битого JSON (как в ricercar_dorian_128.json)
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # Попытка починить: файл имеет вид {"name":..., "style":..., }, {notes...} вне массива
        # Это битый ricercar_dorian_128.json — у него notes закрыт рано и лишние ноты снаружи
        # Починим: найдём первую закрывающую "}," после notes и обрежем мусор
        # Проще: пересоздадим notes из того что есть, обрезав мусор
        # Найдём позицию '"style": null' и обрежем до правильного конца
        # Для этого файла известно: style null, а дальше мусор
        # Удалим всё между ' "style": null\n},' и '{\n            "step":'
        # Самый надёжный — просто перезаписать notes как есть, но починить JSON
        # Удалим дублирующий кусок: найдём '},\n        {\n            "step": 0,\n            "note": "A2"'
        # и заменим на правильное продолжение notes
        # Для универсальности — попробуем json с хвостом отрезать
        # Найдём последний валидный ']' + '}' в конце
        # Проще: если файл битый — пересоздадим минимальный валидный
        print(f"  [!] Битый JSON в {path.name}: {e}, пытаюсь починить...")
        # Попробуем найти последний ']' перед финальным '}'
        # Заменим '},\n        {\n            "step": 0,\n            "note": "A2"' на ',\n        {\n            "step": 0,\n            "note": "A2"'
        # Но надо убрать лишний '},\n'
        # Фактически в файле: после "style": null\n},\n        {\n ... notes ...\n    ],\n    "comment"...
        # Правильно: "style": "...",\n    "notes": [\n        {\n ...\n    ]\n
        # Починим: заменим '"style": null\n},' на '"style": "Renaissance Ricercar Dorian",'
        # и удалим лишнюю '},'
        if '"style": null' in text:
            text = text.replace('"style": null\n},', '"style": "Renaissance Ricercar Dorian",', 1)
            # Теперь в тексте остался лишний '    ],\n    "comment"' — должен быть один
            # Удалим дублирующий '    ],\n    "comment"' если его два
            # Проверим
            try:
                data = json.loads(text)
            except:
                # Последний шанс — взять только до первого '},\n        {' после notes
                # Отрежем хвост начиная с позиции где notes должен закончиться
                # Найдём '"comment": ""' и оставим только его
                idx = text.find('"comment"')
                if idx != -1:
                    # Найдём начало notes
                    notes_start = text.find('"notes": [')
                    if notes_start != -1:
                        # Найдём финальный '    ],\n    "comment"'
                        # Оставим как есть, но удалим лишний '},'
                        # Просто попробуем удалить строку '},' которая стоит перед '        {'
                        text = re.sub(r'\},\n        \{\n            "step": 0,\n            "note": "A2",\n            "duration": "4n"', ',\n        {\n            "step": 0,\n            "note": "A2",\n            "duration": "4n"', text, count=1)
                        data = json.loads(text)
                    else:
                        raise
                else:
                    raise
        else:
            raise

    old_name = data.get("name", "")
    old_style = data.get("style", "")

    # 1. Определить подтип
    subtype = extract_subtype(old_name) or extract_subtype(old_style)
    if not subtype:
        # Попробовать из NON_REN_TO_SUBTYPE по полному имени
        for key, val in NON_REN_TO_SUBTYPE.items():
            if key.lower() in old_name.lower():
                subtype = val
                break
    if not subtype:
        # Fallback: первое слово после Renaissance или первое значимое
        # Для "Renaissance Folia - X" -> Folia уже найдено выше
        # Для остальных — берём первое слово
        subtype = "Ricercar"  # дефолт

    # Нормализуем подтип: первая буква заглавная, остальное как в списке
    # Для Passamezzo Antico — два слова

    # 2. Определить описание
    desc = extract_description(old_name, subtype)
    if not desc or desc.lower() == subtype.lower():
        desc = "Point of Imitation"  # дефолт
    # Капитализируем каждое слово описания
    # Оставим как есть, но первая буква заглавная

    # 3. Определить лад
    mode = determine_mode_for_track(data, subtype)

    # 4. Сформировать новые поля
    new_name = f"Renaissance {subtype} - {desc}"
    new_style = f"Renaissance {subtype} {mode}"

    changed = False
    if old_name != new_name:
        data["name"] = new_name
        changed = True
    if old_style != new_style:
        data["style"] = new_style
        changed = True

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    return {
        "file": path.name,
        "old_name": old_name,
        "new_name": new_name,
        "old_style": old_style,
        "new_style": new_style,
        "changed": changed,
    }


def main():
    files = sorted(LOOPS_DIR.glob("*.json"))
    print(f"Найдено {len(files)} файлов в {LOOPS_DIR}")
    changed_count = 0
    for f in files:
        report = standardize_file(f)
        status = "CHANGED" if report["changed"] else "OK"
        print(f"[{status}] {report['file']}")
        print(f"  name:  '{report['old_name']}' -> '{report['new_name']}'")
        print(f"  style: '{report['old_style']}' -> '{report['new_style']}'")
        if report["changed"]:
            changed_count += 1
    print(f"\nГотово. Изменено {changed_count}/{len(files)} файлов.")


if __name__ == "__main__":
    main()
