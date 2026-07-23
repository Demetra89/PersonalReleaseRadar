# Personal Release Radar — Пятничный музыкальный дайджест-бот

Персональный Telegram-бот для сборки пятничного дайджеста новой музыки:
- **Ветка A (По вкусу)**: Релизы ваших любимых артистов из Spotify (followed + top artists) и похожих из Last.fm.
- **Ветки B и C (Тренды)**: Релизы из Telegram-каналов `@cloudeluxe` (RU cloud/underground) и `@USANEWRAP` (US rap) через RSSHub и Gemini API классификатор.
- **Дедупликация и Сборка**: Дедупликация через PostgreSQL и финальная верстка дайджеста через Gemini API.

---

## 🚀 Архитектура и стек

- **Оркестрация**: n8n (self-hosted в Docker)
- **База данных**: PostgreSQL 16
- **RSS Конвертер**: RSSHub (self-hosted)
- **SSL / Обратный прокси**: Caddy
- **LLM**: Gemini API (Google AI Studio)
- **Уведомления**: Telegram Bot API

---

## 🛠️ Первичное разворачивание на VPS

### 1. Требования
- VPS под управлением Ubuntu 22.04+ (IP: `144.31.148.133`)
- Установленные `docker` и `docker compose`

### 2. Клонирование и настройка переменные окружения
```bash
git clone https://github.com/Demetra89/PersonalReleaseRadar.git /opt/PersonalReleaseRadar
cd /opt/PersonalReleaseRadar
cp .env.example .env
```
Отредактируйте `.env` и укажите необходимые ключи:
- `DOMAIN_NAME`: Ваш домен или DuckDNS адрес.
- `N8N_ENCRYPTION_KEY`: Случайный секретный ключ.
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`: Данные приложения из Spotify Developer Dashboard.
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: Данные Telegram бота и ваш Chat ID.
- `LASTFM_API_KEY`: API ключ Last.fm.
- `GEMINI_API_KEY`: API ключ Google AI Studio.

### 3. Запуск контейнеров
```bash
docker compose up -d
```

---

## 📌 Пошаговый план разработки

1. ✅ **Шаг 1**: Подготовка Docker Compose, Caddyfile, `.env.example`, `init.sql` и разворачивание инфраструктуры на VPS.
2. ⏳ **Шаг 2**: Создание миграций PostgreSQL и проверка таблиц `artists`, `sent_releases`, `seen_telegram_posts`.
3. ⏳ **Шаг 3**: Настройка Spotify Dev Mode приложения и OAuth2 подключения в n8n.
4. ⏳ **Шаг 4**: Построение workflow в n8n (Ветка A -> Ветки B/C -> Merge & Deduplicate -> Gemini Digest -> Telegram).
5. ⏳ **Шаг 5**: Интеграция промптов Gemini (классификатор + дайджест).
6. ⏳ **Шаг 6**: Добавление Error Trigger workflow для алертов об ошибках в Telegram.
7. ⏳ **Шаг 7**: Включение n8n MCP сервера для прямых команд агенту.
