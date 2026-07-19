# ChatList

Python-приложение на PyQt6: один промт — несколько нейросетей, сравнение ответов, сохранение выбранных результатов в SQLite.

## Возможности

- Отправка промта в активные модели (OpenRouter / OpenAI / DeepSeek / Groq и другие OpenAI-совместимые API)
- Временная таблица ответов с выбором строк
- Сохранение отмеченных результатов в БД
- Поиск и сортировка в таблицах UI
- Экспорт в Markdown / JSON
- Настройки (таймаут, параллельность, логирование)
- Лог запросов в `requests.log`

## Требования

- Python 3.11+
- Windows (GUI / сборка exe)

## Установка

```powershell
cd D:\Programs\work\ChatList
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Откройте `.env`. Если OpenRouter с вашего ПК недоступен — используйте прокси Vercel
(см. раздел ниже). Иначе укажите ключ напрямую:

```env
OPENROUTER_API_KEY=ваш_ключ
```

## Прокси Vercel (обход блокировки OpenRouter)

Схема: **GUI и БД локально** → ваш сайт на Vercel → OpenRouter.

1. Задеплойте этот репозиторий на Vercel.
2. В Environment Variables проекта Vercel добавьте:
   - `OPENROUTER_API_KEY` — ключ OpenRouter
   - `CHATLIST_PROXY_SECRET` — любой секретный пароль
   - опционально `OPENAI_BASE_URL=https://openrouter.ai/api/v1`
3. После успеха откройте `https://ваш-проект.vercel.app/api` — должен быть JSON `{"ok": true, ...}`.

```powershell
python main.py
```

## Запуск

```powershell
cd D:\Programs\work\ChatList
python main.py
```

При первом запуске, если таблица моделей пуста, автоматически добавляются модели OpenRouter:

- `openai/gpt-4o-mini` (активна)
- `google/gemini-2.0-flash-001` (активна)
- `anthropic/claude-3.5-haiku` (выключена)

Ключ для них читается из `OPENROUTER_API_KEY` или, если его нет, из `OPENAI_API_KEY`
(удобно, если ключ OpenRouter уже лежит в `OPENAI_API_KEY`).

## Рабочий процесс

1. Введите промт (или выберите сохранённый).
2. Нажмите **Отправить**.
3. Отметьте нужные ответы чекбоксами.
4. Нажмите **Сохранить** — строки попадут в таблицу `results`.
5. При необходимости экспортируйте результаты (**Экспорт…**).

Модели и настройки — кнопки **Модели…** и **Настройки…**.

## База данных

Файл `chatlist.db` (SQLite) создаётся рядом с программой. Схема описана в `DATABASE.md`.

API-ключи **не** хранятся в БД — только имена переменных окружения.

## Сборка exe

```powershell
cd D:\Programs\work\ChatList
python -m PyInstaller --onefile --windowed --name ChatList main.py
```

Исполняемый файл: `dist\ChatList.exe`.  
Рядом с exe положите файл `.env` с ключами (или задайте переменные окружения системы).

## Проверка без GUI

```powershell
cd D:\Programs\work\ChatList
python e2e_check.py
```


| Файл | Назначение |
|------|------------|
| `main.py` | GUI |
| `db.py` | SQLite |
| `models.py` | модели и временная таблица |
| `network.py` | HTTP-запросы к API |
| `export_util.py` | экспорт Markdown/JSON |
| `request_log.py` | лог запросов |
