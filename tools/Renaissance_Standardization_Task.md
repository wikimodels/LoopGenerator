# ТЗ боту: Стандартизация названий и стилей Renaissance-треков

## Назначение
Приведение полей `name` и `style` во всех JSON-треках к единому формату.

## Пути и файлы
- **Входные данные:** `D:\GitHub\LoopGenerator\data\loops\*.json` (32 файла)
  - Поля: `name`, `style`, `bpm`, `instrument`, `steps`, `key`, `scale`, `swing`, `notes[]`, `comment`
- **Скрипт бота:** `D:\GitHub\LoopGenerator\tools\standardize_renaissance.py`
- **Исходное ТЗ:** `C:\Users\Vitali\Downloads\ТЗ для бота_ Переименование треков и стилей.md`
- **Запуск:** из корня `D:\GitHub\LoopGenerator` → `python -X utf8 tools/standardize_renaissance.py`
- **Вывод:** Перезапись тех же JSON на месте (изменённые — `CHANGED`, корректные — `OK`)
- **Зависимости:** Python 3.11+, только стандартная библиотека (`json`, `re`, `pathlib`)

## Правила форматирования

### 1. Поле `name`
- **Шаблон:** `Renaissance [Подвид] - [Название / Описание]`
- Всегда начинается с `Renaissance`
- `[Подвид]` — из списка `SUBTYPES` (Tourdion, Pavane, Folia, Passamezzo, Passamezzo Antico, Ricercar, Canzona, Lamento, Madrigal, Tiento, Romanesca, Sacred Chorale и т.д.; длинные первыми)
- `[Описание]` — текст после ` - ` в исходном `name`, иначе хвост после подтипа

### 2. Поле `style`
- **Шаблон:** `Renaissance [Подвид] [Лад/Тональность]`
- Ровно 3 элемента: `Renaissance` + `[Подвид]` + `[Лад]`
- `[Подвид]` совпадает с `name`
- `[Лад]` — Dorian, Phrygian, Aeolian, Lydian, Mixolydian, Ionian, Major, Minor и т.д.
- Источник лада по приоритету: `name`/`style` → `scale` → анализ `notes` → `DEFAULT_MODE_FOR_SUBTYPE` (напр. Pavane/Folia → Dorian, Lamento → Aeolian) → `Dorian`

### 3. Маппинг не-Renaissance префиксов
`NON_REN_TO_SUBTYPE`: Byzantine/Gothic/Cathedral → Choral/Ricercar/Sacred и т.д. (см. словарь в скрипте)

## Логика скрипта
1. Чтение JSON с починкой битого `ricercar_dorian_128.json` (оборванный `notes`)
2. `extract_subtype()` / `extract_mode()` / `extract_description()` / `determine_mode_for_track()`
3. Сборка `new_name` / `new_style`, сравнение, запись при изменении
4. Лог: `[CHANGED]/[OK] файл: 'old' -> 'new'`

## Примеры
- Было: `Passamezzo Antico - Hypnotic Bass` / `Passamezzo Antico Transposed Dorian`
  Стало: `Renaissance Passamezzo Antico - Hypnotic Bass` / `Renaissance Passamezzo Antico Dorian`
- Было: `Byzantine Choral - G Mixolydian` / `Byzantine Processional Hymn`
  Стало: `Renaissance Choral - G Mixolydian` / `Renaissance Choral Mixolydian`

## Примечание
Все данные уже в JSON и списке треков; внешних запросов не требуется. Для отката — `git diff data/loops` / `git checkout -- data/loops`.
