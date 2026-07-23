# Правила проекта: Пятничный музыкальный дайджест-бот

## 1. Язык и Документация
- Все комментарии в коде, docstrings, коммиты и документация должны быть написаны строго на русском языке.
- Сообщения и описания задачи составляются на русском языке.

## 2. Размещение файлов и скриптов в проекте
- Все вспомогательные скрипты, утилиты деплоя и конфигурации должны создаваться STRICTLY внутри репозитория проекта в папке `scripts/` (например, `scripts/deploy.py`), а НЕ во внешних временных директориях.

## 3. Git Flow & GitHub MCP
- Для всей работы с Git и GitHub (создание веток, PR, коммитов, чтение issues/PR) ОБЯЗАТЕЛЬНО использовать инструменты `github-mcp-server`.
- Все изменения вносятся через feature-ветки и проходят проверку.

## 4. Управление VPS & SSH
- Агент самостоятельно подключается к VPS по SSH для выполнения команд деплоя, работы с Docker Compose, выполнения SQL-миграций в Postgres и проверки логов.
- Скрипт деплоя и настройки SSH доступен в `scripts/deploy.py`.
- Данные VPS:
  - Host/IP: `144.31.148.133`
  - User: `root`
  - OS: Ubuntu 22.04
- Операции с Docker Compose (`docker compose up`, `docker compose ps`, `docker compose logs`) и миграциями Postgres выполняются непосредственно на VPS через SSH.

## 5. Стек Технологий и Инфраструктура
- **Оркестрация**: n8n (self-hosted v2.18.4+ в docker-compose на VPS).
- **База данных**: PostgreSQL (отдельная схема/таблицы для проекта: `artists`, `sent_releases`, `seen_telegram_posts`).
- **RSS Конвертер**: RSSHub (self-hosted в docker-compose) для превращения Telegram-каналов (`@cloudeluxe`, `@USANEWRAP`) в RSS без official API.
- **Интеграция Spotify**: Spotify Web API в Dev Mode (Ограничение Dev Mode: НЕ использовать `/recommendations`, `/related-artists`, `/audio-features`, `/browse/new-releases`, `/artists/{id}/top-tracks`. Использовать ТОЛЬКО `/me/following`, `/me/top/artists`, `/artists/{id}/albums`).
- **Расширение вкуса**: Last.fm API (`artist.getSimilar`).
- **LLM / AI**: Gemini API (Google AI Studio) для:
  1. Классификации постов Telegram-каналов (фильтр релизов).
  2. Сборки финального текста дайджеста по секциям в Markdown для Telegram.
- **Уведомления**: Telegram Bot API (отправка дайджеста и алертов об ошибках в основной workflow).
- **Интеграция n8n MCP**: Включение instance-level MCP в n8n для прямого управления workflow агентом.

## 6. Схема базы данных проекта
```sql
CREATE TABLE IF NOT EXISTS artists (
  id SERIAL PRIMARY KEY,
  spotify_id TEXT,
  name TEXT NOT NULL,
  source TEXT NOT NULL,        -- followed / top / similar
  added_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sent_releases (
  id SERIAL PRIMARY KEY,
  artist_name TEXT NOT NULL,
  track_title TEXT NOT NULL,
  source TEXT NOT NULL,        -- taste / ru_cloud / us_rap
  release_date DATE,
  sent_at TIMESTAMP DEFAULT now(),
  UNIQUE (artist_name, track_title)
);

CREATE TABLE IF NOT EXISTS seen_telegram_posts (
  id SERIAL PRIMARY KEY,
  channel TEXT NOT NULL,
  message_id TEXT NOT NULL,
  processed_at TIMESTAMP DEFAULT now(),
  UNIQUE (channel, message_id)
);
```

## 7. Процесс разработки (Микро-спринты)
- Работать строго по шагам. Не создавать гигантские куски кода за один раз.
- Показывать результат каждого шага перед тем как двигаться дальше.
- Код должен быть готовым к продакшену (без заглушек `// todo`).
- Все миграции БД должны иметь рабочую обратную часть или идемпотентные проверки.
