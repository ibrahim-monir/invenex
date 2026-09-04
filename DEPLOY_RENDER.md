# Invenex live kora — Render.com (free, card lage na)

Apnar data ekhon Google Drive + Sheet e thake, tai host ta "disposable" —
server muche gele-o data jay na. Sei jonno Render er free tier-i jothesto.

**Free tier:** card lage na, expiry nei, 750 hour/month (ekta app 24/7 chalanor
jonno jothesto)। Ekta-i jhamela — 15 minute keu na dhukle app ghumiye jay, ar
porer visitor ke ~1 minute wait korte hoy। Tarpor normal speed.

Ghumiye gele data harabe **na** — chalu howar somoy app nijei Drive theke
database ta tene ane (test kore dekha hoyeche)।

---

## 1. Age: code ta GitHub e push korun

```bash
git add -A
git commit -m "Add Google Drive/Sheets backup and Render deploy config"
git push
```

`service-account.json`, `.env` ar `render-service-account-oneline.txt` —
egulo `.gitignore` e ache, tai push hobe na। **Thik-i ache** — ei gulo Render e
env var hisebe diben, file hisebe na.

---

## 2. Render e web service banano

1. https://render.com e **GitHub diye Sign up** korun (card chaibe na)।
2. **New +** → **Web Service** → apnar `invenex` repo ta connect korun।
3. Settings:

   | Field | Value |
   |---|---|
   | **Language** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:$PORT app:app` |
   | **Instance Type** | **Free** |

   > **`--workers 1` ta obosshoi rakhben.** Ekadhik worker hole protita nijer
   > moto kore database rakhbe ar ekjon onnojoner upload muche debe.

---

## 3. Environment variables

Render dashboard → apnar service → **Environment** → **Add Environment Variable**।
Ei gulo ek ek kore boshan:

| Key | Value |
|---|---|
| `SECRET_KEY` | ekta lomba random string (nicher command diye banate paren) |
| `ADMIN_USERNAME` | apnar login username |
| `ADMIN_PASSWORD` | apnar login password — **notun ekta din** |
| `ADMIN_DISPLAY_NAME` | `Nishat Urmi` |
| `GDRIVE_FOLDER_ID` | `1wGTuZzS3E4j9MQczCCJGaQ2fZEn4C7cl` |
| `GSHEET_ID` | `1DjWEvAii71mVUuFxfB0PS3UEx30eKDVwv_Dpb93CutI` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | `render-service-account-oneline.txt` file er **puro line ta** copy kore paste korun |
| `PYTHON_VERSION` | `3.12.10` |

**Ja diben NA:**
- `GOOGLE_SERVICE_ACCOUNT_FILE` — server e oi file thakbe na
- `DATABASE_URL` — khali rakhben, tahole SQLite + Drive backup chalu thakbe

Notun `SECRET_KEY` banate:

```bash
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 4. Deploy

**Create Web Service** e click korun. Prothom build e 2-3 minute lagbe.

Live hole URL pabe emon: `https://invenex.onrender.com`

Prothombar chalu howar somoy server e kono database thakbe na — app nijei Drive
theke `invenex.db` name nebe, tai apnar data ekdom jekhane chilo sekhan thekei
shuru hobe.

**Log e ei duita line khujben** (Render dashboard → **Logs**):

```
[backup] restored /opt/render/project/src/data/invenex.db from Google Drive
[backup] enabled -> Drive + Sheets
```

---

## 5. Deploy er por check korun

1. URL e giye login korun।
2. Ekta test income entry add korun।
3. **10 second wait korun**, tarpor Google Drive e `invenex.db` file er
   "Modified" time ta dekhun — ekhon-i update howa uchit।
4. 5 minute por Google Sheet ta refresh korun — notun row ta dekhte paben।

Ei tinta mille bujhben pura chain kaj korche।

---

## Pore code bodlale

GitHub e push korlei Render nijei abar deploy kore dey — alada kichu korte hobe na।

---

## Mone rakhben

- **15 minute nishchup thakle app ghumay।** Client ke bole rakhben prothom
  page ta khulte ~1 minute lagte pare। Data er kono khoti hoy na।
- Ghumanor age Render `SIGTERM` pathay, ar app tokhon sesh obostha ta Drive e
  upload kore niye tarpor bondho hoy।
- **Ekta-i instance** cholbe (free tier e emni-i ekta)। Kokhono paid tier e
  gie worker barale Drive backup bhenge jabe — tokhon Postgres e jete hobe।
- Render er **nijer free Postgres 30 din por muche jay** — oita use korben na।
  Apnar data Drive/Sheet e-i thakuk।
- Ekhon `service-account.json` ar oi one-line file ta apnar computer e ache।
  Egulo keu peye gele apnar oi folder ar sheet e dhukte parbe — kauke pathaben na।
