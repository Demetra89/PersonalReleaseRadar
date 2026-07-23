-- Инициализация таблиц для Музыкального Дайджест-Бота

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
