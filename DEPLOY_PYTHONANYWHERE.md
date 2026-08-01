# Deploy Invenex on PythonAnywhere (free, ~10 minutes)

PythonAnywhere username: **invenex**
Live URL (once deployed): **https://invenex.pythonanywhere.com**

A ready-to-upload zip is already prepared at:
`E:\laragon\www\invenex\invenex.zip`

## 1. Upload the zip
- Log in to PythonAnywhere, go to the **Files** tab.
- Click **Upload a file**, select `invenex.zip` from your computer, upload it into
  your home directory (`/home/invenex/`).

## 2. Open a Bash console and unzip
- Go to the **Consoles** tab → click **Bash**.
- Run:
  ```bash
  unzip invenex.zip -d invenex
  cd invenex
  mkvirtualenv --python=/usr/bin/python3.10 invenex-env
  pip install -r requirements.txt
  ```
  (`mkvirtualenv` automatically activates the new virtualenv — you'll see
  `(invenex-env)` in the prompt.)

## 3. Create the web app
- Go to the **Web** tab → **Add a new web app** → Next → choose **Manual configuration**
  → pick **Python 3.10** → Next.
- On the resulting config page, set:
  - **Source code:** `/home/invenex/invenex`
  - **Working directory:** `/home/invenex/invenex`
  - **Virtualenv:** `/home/invenex/.virtualenvs/invenex-env`

## 4. Set your login credentials + secret key
- Still on the **Web** tab, click the **WSGI configuration file** link (opens an editor).
- Delete everything in it and paste this exactly:

  ```python
  import os
  import sys

  # ---- set your own values here ----
  os.environ["SECRET_KEY"] = "38653f493af6e8aaa00574a701678bc8d79080532382e089"
  os.environ["ADMIN_USERNAME"] = "admin"
  os.environ["ADMIN_PASSWORD"] = "Invenex@2026"
  os.environ["ADMIN_DISPLAY_NAME"] = "Nishat Urmi"
  # -----------------------------------

  path = "/home/invenex/invenex"
  if path not in sys.path:
      sys.path.insert(0, path)

  from app import app as application
  ```
- (Optional) change `ADMIN_PASSWORD` to whatever you'd like — this is the password
  you and your client will log in with.
- Save the file.

## 5. Reload and open the site
- Go back to the **Web** tab, click the green **Reload** button.
- Open **https://invenex.pythonanywhere.com** — log in with
  `admin` / `Invenex@2026` (or whatever password you set in step 4).

That's the permanent live URL to share with your client — it stays up even when
your PC is off.

## Data storage note
The app uses a local SQLite file (`data/invenex.db`) created automatically inside the
`invenex` folder the first time it runs. PythonAnywhere's disk storage is permanent
(not wiped between reloads), so your inventory/income/expense data stays safe across
reloads and restarts.

## Updating the app later
When you make code changes: re-zip and re-upload, unzip over the old folder
(`unzip -o invenex.zip -d invenex`), then hit **Reload** on the Web tab again.
