# Google Drive + Sheets backup — setup

Apnar data duijaygay thakbe, dutoi **apnar nijer Google account e**:

| Kothay | Ki thake | Kaje lage |
|---|---|---|
| **Drive folder** | `invenex.db` — asol database file. Prottek diner ekta version Drive er **version history** te pin kora thake (default sesh **14 din**) | Ekdom exact restore. Host mure gele ei file diyei sob ferot ashe |
| **Google Sheet** | protita table ekta alada tab e (items, sales, purchases, income, expenses...) | Apni nijei khule data dekhte parben. Drive-o jodi na thake, Sheet theke database rebuild kora jay |

App chalu howar somoy Drive theke database name (jodi local e na thake), ar
protita save er **~5 second** por abar Drive e upload hoy. Sheet refresh hoy
prottek **5 minute** e. Kichu configure na korle app agher motoi chole — kono
error hobe na.

**Card lage na.** Google Cloud e project baniye Sheets/Drive API on kora ar
service account banano — sob free, billing account chara.

---

## 1. Google Cloud e service account banano (ekbar, ~5 minute)

1. https://console.cloud.google.com e jan (apnar normal Gmail diyei login)।
2. Upore project dropdown → **New Project** → naam din `invenex-backup` → **Create**।
3. Bam pashe **APIs & Services → Library**। Ekhane duita API on korte hobe:
   - `Google Drive API` khujun → **Enable**
   - `Google Sheets API` khujun → **Enable**
4. **APIs & Services → Credentials** → **Create Credentials** → **Service account**।
   - Name: `invenex-backup` → **Create and Continue** → role kichu dite hobe na →
     **Done**।
5. Toiri howa service account tay click korun → **Keys** tab → **Add Key** →
   **Create new key** → **JSON** → **Create**।
   Ekta `.json` file download hobe.
6. Oi file ta project folder e `service-account.json` naam e rakhun।
   (`.gitignore` e already add kora ache, tai bhule GitHub e chole jabe na।)
7. Oi JSON file ta khulun, `client_email` field ta copy korun — dekhte emon:
   `invenex-backup@invenex-backup-123456.iam.gserviceaccount.com`
   **Ei email ta porer step e lagbe.**

---

## 2. Drive folder banano ar share kora

1. https://drive.google.com e ekta folder banan, naam din `Invenex Backup`।
2. Folder e right-click → **Share** → upore step 1.7 er **client_email** ta paste
   korun → permission **Editor** din → **Send**।
   (Warning ashte pare je eta apnar contact na — thik ache, egiye jan।)
3. Folder ta khulun ar browser er address bar dekhun:
   `https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQr`
   Sesher oi lomba code ta-i apnar **folder ID**।

> **Gurutbopurno:** service account er nijer kono Drive storage nei, tai se
> **notun file toiri korte pare na** — folder share kora thakleo na. Se shudhu
> **already thaka** file er content bodlate pare (tokhon storage apnar
> malikanay, apnar 15 GB theke jay)।
>
> Tai folder e **ekbar** `invenex.db` naam e ekta file apnake nije upload kore
> rakhte hobe (khali text file holeo chole)। Erpor app ta oi file tai barbar
> update korbe — ar kono file toiri korte hobe na।

---

## 3. Google Sheet banano ar share kora (optional, kintu recommend kori)

1. https://sheets.new e ekta notun spreadsheet banan, naam din `Invenex Data`।
2. **Share** → oi same **client_email** → **Editor** → **Send**।
3. Address bar theke ID nin:
   `https://docs.google.com/spreadsheets/d/1XyZ.../edit` → majher oi code ta
   apnar **sheet ID**।

Tab gulo app nijei baniye nebe — apnake kichu banate hobe na.

---

## 4. `.env` e boshano

```env
GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
GDRIVE_FOLDER_ID=ekhane_folder_id
GSHEET_ID=ekhane_sheet_id
```

Test korun:

```bash
.venv\Scripts\python restore_backup.py status
.venv\Scripts\python restore_backup.py push      # Drive e upload
.venv\Scripts\python restore_backup.py sheets    # Sheet e likhbe
.venv\Scripts\python restore_backup.py list      # Drive e ki ki ache
```

`push` er por Drive e `invenex.db` file tar size bere jabe (apnar data soho)।
`sheets` er por spreadsheet e 9 ta tab toiri hobe.

Erpor `python app.py` chalale sob **automatic** — alada kichu korte hobe na.

---

## 5. Host e (Render ityadi) boshano

Server e file rakha jay na, tai JSON tar **content** ta env var e diben:

- `GOOGLE_SERVICE_ACCOUNT_JSON` — `service-account.json` er **puro text**, ek
  line e paste kore din
- `GDRIVE_FOLDER_ID` — same
- `GSHEET_ID` — same
- `GOOGLE_SERVICE_ACCOUNT_FILE` — **diben na**

Notun host e prothombar chalu hole local e kono database thakbe na, tai app
nijei Drive theke `invenex.db` name nebe — data ekdom jekhane chilo sekhan
thekei chalu hobe.

---

## Data ferot anar niyom

**Drive theke (exact, ei ta age try korben):**

```bash
python restore_backup.py pull
```

Purono local file ta `data/invenex.db.replaced` naam e theke jabe.

**Purono kono diner obosthay ferot jete:** Drive e `invenex.db` file e right-click
→ **File information** → **Manage versions**। Ekhane prottek diner pin kora version
dekhben — jeta lagbe seta **Download** kore `data/invenex.db` naam e boshiye din।

**Sheet theke (jodi Drive-o na thake):**

```bash
python restore_backup.py from-sheets
```

Sob table Sheet theke pore database ta notun kore banabe, tarpor Drive e upload
kore debe.

---

## Jante hobe emon kichu kotha

- **Ekta-i app instance** cholte parbe. Duita ekshathe likhle ekjon onnojoner
  upload muche debe. Render free e ekta-i chole, tai somossa nei।
- Puro file protibar upload hoy, tai database chhoto thakle-i bhalo. Apnar db
  ekhon **192 KB** — kayek bochorer data teo kayek MB, kono somossa nei।
- Upload er thik majhkhane server crash korle sesh entry ta miss hote pare।
  Sei jonnoi diner version pin kora thake — agher diner obostha bhalo thake।
- Sheet e nije hate edit korle seta app e ferot ashe **na**। Sheet ta dekhar
  jonno ar last-resort backup hisebe — `from-sheets` chalale tokhon-i oi edit
  database e dhukbe।
- `service-account.json` keu peye gele apnar oi folder ar sheet e dhukte parbe।
  File ta GitHub e push korben na (`.gitignore` e ache)। Bhul kore geleo Google
  Cloud → Credentials theke key ta delete kore notun banano jay।
- Kono din backup off korte chaile `.env` theke `GDRIVE_FOLDER_ID` ar `GSHEET_ID`
  khali kore diben — app agher motoi cholbe।

---

## Setting gulo

| Env var | Default | Ki kore |
|---|---|---|
| `GDRIVE_FOLDER_ID` | *(khali)* | khali = Drive backup off |
| `GSHEET_ID` | *(khali)* | khali = Sheet mirror off |
| `GDRIVE_DB_NAME` | `invenex.db` | Drive e file er naam |
| `BACKUP_DEBOUNCE_SECONDS` | `5` | eksathe onek save hole eto second wait kore ekbar upload |
| `GDRIVE_SNAPSHOT_KEEP` | `14` | koto diner version pin kore rakhbe |
| `SHEET_SYNC_SECONDS` | `300` | Sheet koto por por refresh hobe |
