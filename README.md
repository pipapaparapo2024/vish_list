## vish_list — социальный вишлист и совместные подарки

Веб‑приложение, которое позволяет:

- создавать личные вишлисты с событиями (день рождения, праздник и т.п.);
- публиковать списки по публичной ссылке и делиться ими с друзьями;
- бронировать подарки гостями, чтобы не дублировать покупки;
- организовывать совместные денежные сборы на один подарок;
- отслеживать прогресс по каждому подарку в реальном времени;
- смотреть мероприятия и подарки друзей.

Проект состоит из **backend на FastAPI** и **frontend на Next.js (App Router, TypeScript)** и разворачивается одной командой через Docker Compose.

---

## Стек

- **Frontend**
  - Next.js 14 (App Router, TypeScript)
  - React
  - Jest + Testing Library для тестов
  - sonner для toast‑уведомлений
  - lucide‑react для иконок

- **Backend**
  - FastAPI
  - PostgreSQL (через SQLAlchemy + psycopg2)
  - Alembic для миграций
  - JWT‑авторизация
  - WebSocket для обновления вишлистов и подарков в реальном времени

---

## Быстрый старт через Docker

Требования:

- Docker и Docker Compose

Из корня репозитория:

```bash
docker compose up
```

Что произойдёт:

- поднимется PostgreSQL (порт `5433` на вашей машине);
- backend запустится на `http://localhost:8000`;
- frontend запустится на `http://localhost:3000`.

После первого старта данные будут пустыми — создайте пользователя и вишлист через веб‑интерфейс.

Остановить всё:

```bash
docker compose down
```

---

## Запуск без Docker (локально)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и при необходимости измените параметры подключения к PostgreSQL:

```env
POSTGRES_USER=wishlist
POSTGRES_PASSWORD=wishlist
POSTGRES_DB=wishlist
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
```

Запустите сервер:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Доступные основные эндпоинты (неполный список):

- `GET /api/v1/auth/me` — информация о текущем пользователе;
- `POST /api/v1/auth/register`, `POST /api/v1/auth/login` — регистрация и вход;
- `GET /api/v1/wishlists` и `POST /api/v1/wishlists` — работа с личными вишлистами;
- `GET /api/v1/public/wishlists/{share_slug}` — публичный просмотр списка;
- `POST /api/v1/public/wishlists/{share_slug}/items/{item_id}/reserve` — бронирование подарка;
- `POST /api/v1/public/wishlists/{share_slug}/items/{item_id}/contributions` — совместный сбор.

### Frontend

```bash
cd frontend
npm install
```

Убедитесь, что в `frontend/.env.local` или переменных окружения задан адрес backend (для dev окружения он уже прокинут через Docker Compose):

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Запуск dev‑сервера:

```bash
npm run dev
```

Приложение будет доступно по адресу `http://localhost:3000`.

---

## Основные сценарии использования

- **Создание вишлиста**
  - Зарегистрируйтесь и войдите в систему.
  - Создайте событие и добавьте подарки.
  - Включите публичный доступ и отправьте ссылку друзьям.

- **Резервирование подарков и совместные сборы**
  - Гость открывает публичную ссылку `/w/{slug}`.
  - Может забронировать конкретный подарок или внести сумму в совместный сбор.
  - Состояние подарка и прогресс по сбору обновляются в реальном времени у всех зрителей.

- **События друзей**
  - В разделе друзей просматриваются публичные мероприятия и подарки знакомых.

---

## Тесты и качество кода

### Frontend

```bash
cd frontend
npm test       # юнит‑тесты (Jest)
npm run lint   # ESLint
```

### Backend

```bash
cd backend
pytest
```

---

## Структура репозитория

- `backend/` — FastAPI‑приложение, модели, схемы, API, real‑time менеджер.
- `frontend/` — Next.js‑приложение (страницы, компоненты, хуки, тесты).
- `docker-compose.yml` — запуск всей системы одной командой.
- `prompts.md` — хронология этапов разработки проекта.

