# HREC – AI HR & Recruitment System (Desktop SaaS)

Production-style desktop app built with:
- **Frontend**: HTML/CSS/Vanilla JS + Chart.js
- **Backend**: Python Flask REST API
- **Database**: MongoDB Atlas (pymongo)
- **Desktop wrapper**: Electron
- **AI**: TF-IDF + cosine similarity (resume screening) + basic NLP scoring (interview), with optional OpenAI enrichment

## Project structure

- `client/` – UI (`index.html`, `dashboard.html`, `styles.css`, `script.js`)
- `server/` – Flask API (`app.py`, `routes/`, `utils/`, `models/`)
- `electron/` – Electron entry (`main.js`, `preload.js`)

## 1) Configure environment

Set your MongoDB Atlas URI (required):

- **Windows PowerShell**

```powershell
$env:HREC_MONGODB_URI="mongodb+srv://<USERNAME>:<PASSWORD>@hrec-cluster.mongodb.net/hrec_db"
```

Optional:
- `HREC_SECRET_KEY` – JWT signing secret
- `HREC_HOST` (default `127.0.0.1`)
- `HREC_PORT` (default `5000`)
- `OPENAI_API_KEY` – enables OpenAI-powered resume analysis + interview questions/feedback (optional)
- `OPENAI_MODEL` – model name (default `gpt-4o-mini`)

### OpenAI fallback behavior
OpenAI is an optional enhancement. If `OPENAI_API_KEY` is missing/empty (or the OpenAI call fails), the app automatically falls back to the existing local logic:
- Resume screening: TF-IDF + cosine similarity
- Interview chatbot: local heuristic question generation + keyword/length scoring + basic feedback

## 2) Install backend deps

```powershell
python -m pip install -r server\requirements.txt
```

### Sample `.env`
Create/update your project `.env` file like:

```env
HREC_MONGODB_URI=mongodb+srv://<USERNAME>:<PASSWORD>@hrec-cluster.mongodb.net/hrec_db?retryWrites=true&w=majority&appName=hrec-cluster
JWT_SECRET=your-secret

# Optional (enables OpenAI enrichment):
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o-mini
```

## 3) Run Flask (web)

```powershell
python server\app.py
```

Open `http://127.0.0.1:5000/`.

## 4) Run as desktop app (Electron)

Install Node deps:

```powershell
npm install
```

If `npm` is not found, install **Node.js LTS** first.

Start desktop app:

```powershell
npm start
```

Electron will spawn the Flask server and load the UI.

## Roles

Register/login with one of:
- **HR**: post jobs, review candidates, accept/reject, schedule interviews, assign tasks, update performance, view charts
- **Candidate**: view jobs, apply, upload resume (scored), AI interview chatbot, view application status
- **Employee**: view tasks, update task status, view performance + HR feedback

## Notes

- **Resume upload** supports **PDF** and **DOCX**.
- **Google login** and **SMTP email** are placeholders (ready for real OAuth/SMTP env vars).

