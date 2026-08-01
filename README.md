# Invenex

Simple Inventory + Income + Expense tracker.

- **Inventory** — add items, manually log stock in/out (koto pcs kome gelo, koto pcs royeche), low-stock alerts.
- **Income** — log entries by purpose (amount + date + note).
- **Expense** — log entries by purpose (amount + date + note).
- **Dashboard** — total income, total expense, balance, low-stock items, recent activity.
- Single admin login (username/password from environment variables).

Built with Flask + SQLAlchemy. Works with SQLite (local) or Postgres (production).

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
copy .env.example .env          # then edit .env: set ADMIN_USERNAME / ADMIN_PASSWORD / SECRET_KEY

python app.py
```

Open http://127.0.0.1:5000 and log in with the username/password you set in `.env`.

Local data is stored in `data/invenex.db` (SQLite) — nothing to configure.

## Deploy for free (Render + Neon Postgres)

Render's free web services don't keep a persistent disk, so SQLite data can be lost on
redeploy. To keep your data safe permanently, use a free Postgres database from
**Neon.tech** together with a free **Render.com** web service. Both have no-credit-card
free tiers.

### 1. Push this project to GitHub

Create a new GitHub repo and push this folder to it (ask me if you want help with this step).

### 2. Create a free Postgres database (Neon.tech)

1. Sign up at https://neon.tech (free, no credit card).
2. Create a new project.
3. Copy the **connection string** it gives you (starts with `postgresql://...`).

### 3. Create the web service (Render.com)

1. Sign up at https://render.com (free, GitHub login works).
2. Click **New +** → **Web Service** → connect your GitHub repo.
3. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Instance Type:** Free
4. Add Environment Variables (Render dashboard → Environment):
   - `SECRET_KEY` — any long random string
   - `ADMIN_USERNAME` — your chosen login username
   - `ADMIN_PASSWORD` — your chosen login password
   - `DATABASE_URL` — the Neon connection string from step 2
5. Click **Create Web Service**. Render will build and deploy automatically.

You'll get a free URL like `https://invenex.onrender.com`.

**Note:** on Render's free tier the app "sleeps" after ~15 minutes of no traffic and
takes a few seconds to wake up on the next visit — normal for free hosting, doesn't
affect your data.

### Updating the live app later

Just push new commits to GitHub — Render redeploys automatically.
