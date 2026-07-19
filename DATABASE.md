# Схема базы данных ChatList

СУБД: **SQLite**. Доступ к БД инкапсулирован в модуле `db.py`.

API-ключи **не хранятся** в БД. В таблице `models` хранится только имя переменной окружения (`api_key_env`); сами ключи лежат в файле `.env`.

---

## Диаграмма связей

```
prompts 1 ──< results >── 1 models
settings (независимая)
```

---

## Таблица `prompts`

Запросы пользователя.

| Поле        | Тип          | Ограничения              | Описание                          |
|-------------|--------------|--------------------------|-----------------------------------|
| `id`        | INTEGER      | PRIMARY KEY, AUTOINCREMENT | Идентификатор промта            |
| `created_at`| TEXT         | NOT NULL                 | Дата/время создания (ISO 8601)    |
| `text`      | TEXT         | NOT NULL                 | Текст промта                      |
| `tags`      | TEXT         | NULL                     | Теги (строка, например через `,`) |

**Индексы (рекомендуемые):** по `created_at`, при необходимости — по `tags`.

---

## Таблица `models`

Нейросети (провайдеры API).

| Поле          | Тип     | Ограничения              | Описание                                      |
|---------------|---------|--------------------------|-----------------------------------------------|
| `id`          | INTEGER | PRIMARY KEY, AUTOINCREMENT | Идентификатор модели                        |
| `name`        | TEXT    | NOT NULL, UNIQUE         | Отображаемое имя (например, `GPT-4o`)         |
| `api_url`     | TEXT    | NOT NULL                 | URL endpoint API                              |
| `api_key_env` | TEXT    | NOT NULL                 | Имя переменной в `.env` (не сам ключ)         |
| `is_active`   | INTEGER | NOT NULL, DEFAULT 1      | `1` — участвует в запросах, `0` — отключена   |

**Примечание:** в спецификации поле названо `api-id`; в схеме оно представлено как `api_key_env` — имя переменной окружения с ключом.

**Запросы:** активные модели выбираются условием `WHERE is_active = 1`.

---

## Таблица `results`

Сохранённые (отмеченные пользователем) ответы.

| Поле         | Тип     | Ограничения                         | Описание                          |
|--------------|---------|-------------------------------------|-----------------------------------|
| `id`         | INTEGER | PRIMARY KEY, AUTOINCREMENT          | Идентификатор записи              |
| `prompt_id`  | INTEGER | NOT NULL, FK → `prompts(id)`        | Связанный промт                   |
| `model_id`   | INTEGER | NOT NULL, FK → `models(id)`         | Модель, давшая ответ              |
| `response`   | TEXT    | NOT NULL                            | Текст ответа                      |
| `created_at` | TEXT    | NOT NULL                            | Дата/время сохранения (ISO 8601)  |

**Внешние ключи:** при удалении промта/модели поведение задаётся в коде (`ON DELETE` — по необходимости CASCADE или запрет удаления при наличии результатов).

---

## Таблица `settings`

Настройки программы (ключ–значение).

| Поле    | Тип  | Ограничения        | Описание                |
|---------|------|--------------------|-------------------------|
| `key`   | TEXT | PRIMARY KEY        | Имя настройки           |
| `value` | TEXT | NULL               | Значение настройки      |

Примеры ключей: `window_width`, `theme`, `default_tags` и т.п.

---

## Временная таблица результатов (не в SQLite)

Хранится **только в памяти** на время сессии сравнения. В БД не создаётся.

| Поле       | Тип     | Описание                                      |
|------------|---------|-----------------------------------------------|
| `model`    | str     | Имя модели                                    |
| `response` | str     | Текст ответа (или сообщение об ошибке)        |
| `selected` | bool    | Отмечена ли строка для сохранения             |

**Жизненный цикл:**
1. Создаётся после получения ответов от активных моделей.
2. При «Сохранить» строки с `selected = True` пишутся в `results`, затем таблица очищается.
3. При новом запросе таблица удаляется и создаётся заново.

---

## Пример DDL

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL,
    text       TEXT    NOT NULL,
    tags       TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    api_url     TEXT    NOT NULL,
    api_key_env TEXT    NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id  INTEGER NOT NULL,
    model_id   INTEGER NOT NULL,
    response   TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id),
    FOREIGN KEY (model_id)  REFERENCES models(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
```

---

## Пример `.env`

```env
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=...
GROQ_API_KEY=...
```

В `models.api_key_env` тогда хранятся значения вроде `OPENAI_API_KEY`, а не сами ключи.
