# Переименование файлов: Neoclassical Lydian конвенция

## Назначение
Приведение `name`/`style` лидийских неоклассических треков к новой единой конвенции.

## Область
- **Входные файлы:** `D:\GitHub\LoopGenerator\data\loops\neoclassical*_lydian*.json` + любые `*lydian*.json` с `style` содержащим `neoclassical` (Lydian)
- **Альтернативно:** весь `data/loops` с фильтром `style`/`name` содержит `lydian` (case-insensitive)
- **Скрипт:** `tools/rename_neoclassical_lydian.py` (создать по этому ТЗ)
- **Запуск:** `python -X utf8 tools/rename_neoclassical_lydian.py`

## 1. Поле `name` — новая конвенция

**Шаблон:** `Neoclassical Lydian - {unique name}`

- Всегда префикс `Neoclassical Lydian - ` (с дефисом и пробелами как показано)
- `{unique name}` — уникальная часть из исходного имени (часть после ` - `, либо всё имя без префикса)
- **Ограничение длины:** максимальная длина всей строки `name` = длина фразы:
  `Neoclassical Piano Loop - Call-and-Response (Eb Lydian, Frost)` (59 символов)
  - Если `{unique name}` длиннее — обрезать до лимита, сохраняя целые слова
  - Подсчёт — по символам всей строки `name`

**Примеры:**
- Было: `Neoclassical Lydian Arpeggio - Frost Pattern` → Стало: `Neoclassical Lydian - Frost Pattern`
- Было: `Neoclassical Piano Loop - Call-and-Response (Eb Lydian, Frost)` → Стало: без изменений (эталон максимума)

## 2. Поле `style` — чистка

- **Удалить** слово `neoclassical` (case-insensitive) из `style`
- Оставить остаток как есть: `lydian arpeggio`, `lydian frost pattern` и т.д.
- Нормализовать: трим пробелов, схлопнуть двойные пробелы, `lydian` — с маленькой буквы, если был с большой — оставить как в оригинале? Рекомендуется lower: `lydian arpeggio`
- Если после удаления пусто — поставить `lydian`

**Примеры:**
- Было: `Neoclassical Lydian Arpeggio` → Стало: `lydian arpeggio`
- Было: `Neoclassical Lydian Frost` → Стало: `lydian frost`

## Логика скрипта
1. Найти файлы-кандидаты (`lydian` в `name`/`style`/`filename`)
2. Для каждого:
   a. `unique = original_name.split(" - ", 1)[1] if " - " in name else name.replace("Neoclassical", "").strip(" -")`
   b. `new_name = f"Neoclassical Lydian - {unique}"` → обрезать до 59 символов
   c. `new_style = re.sub(r"(?i)\bneoclassical\b", "", old_style).strip()` → схлопнуть пробелы, fallback `lydian`
3. Записать JSON обратно (`ensure_ascii=False, indent=4`)
4. Лог: `[CHANGED] file: 'old name' -> 'new name' | 'old style' -> 'new style'`

## Примечание
- `instrument`, `notes`, `key`, `scale` не трогать
- Обработка `#` → `_Sharp_` уже выполнена отдельно (см. `Renaissance_Standardization_Task.md`)
