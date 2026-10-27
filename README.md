# TRINETRA — Starter Kit
Team ASDG Innovators | SIH26070

This is Phase 1 of the build: environment + repo skeleton. Everything here is set up
for a **Windows dev machine** doing backend/frontend work locally, while **model
training happens remotely** (Google Colab or a rented GPU box) — you never need a
GPU on your own laptop.

---

## 1. Install core tools (once, on your Windows machine)

Install these in order:

1. **Git for Windows** — https://git-scm.com/download/win
2. **Python 3.11** — https://www.python.org/downloads/ (check "Add python.exe to PATH" during install)
3. **Node.js LTS (v20+)** — https://nodejs.org/
4. **Docker Desktop** — https://www.docker.com/products/docker-desktop/
   - During install, let it enable **WSL2** — this is what lets Docker run properly on Windows.
5. **VS Code** — https://code.visualstudio.com/ (install the Python and Docker extensions once it's open)

Verify everything installed correctly by opening PowerShell and running:
```powershell
git --version
python --version
node --version
docker --version
```
All four should print a version number. If `docker --version` fails, restart your machine once — Docker Desktop needs a reboot after first install.

---

## 2. Get this starter kit into a real Git repo

```powershell
cd path\to\where\you\keep\projects
mkdir trinetra
cd trinetra
git init
```
Copy all the files from this starter kit into that `trinetra` folder, then:
```powershell
git add .
git commit -m "Initial project skeleton"
```
Push it to a GitHub repo (create an empty one on github.com first, then):
```powershell
git remote add origin https://github.com/<your-username>/trinetra.git
git branch -M main
git push -u origin main
```
Do this now, even before writing more code — everyone on the team should be pulling from this repo from day one.

---

## 3. Local backend environment (lightweight — NOT for training)

This env is just for running the FastAPI backend and testing API endpoints locally.
It does **not** need PyTorch or GPU libraries — those live in `ml/requirements.txt`
and only get installed on Colab / your rented GPU box.

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

You'll know it worked if `(venv)` appears at the start of your PowerShell prompt.

---

## 4. Database (Postgres + PostGIS) via Docker

From the project root (where `docker-compose.yml` lives):
```powershell
docker compose up -d db
```
Check it's running:
```powershell
docker ps
```
You should see a `postgis/postgis` container listed as `Up`. This is your one database
for both cyclone records and geospatial cone data — no separate DB setup needed.

---

## 5. Run the backend

Still with your `venv` activated:
```powershell
cd backend
copy ..\.env.example ..\.env
uvicorn app.main:app --reload --port 8000
```
Open **http://localhost:8000/health** in a browser — you should see `{"status": "ok"}`.
That confirms your backend, and its connection to the database, both work.

---

## 6. Training environment — Colab (free, start here)

1. Push your repo to GitHub (step 2) — Colab will clone it directly.
2. Open `ml/notebooks/trinetra_training_starter.ipynb` in Google Colab
   (Colab → File → Upload notebook, or open it from GitHub directly via Colab's
   "GitHub" tab).
3. In Colab: **Runtime → Change runtime type → GPU (T4 is fine to start)**.
4. Run the first cell — it clones your repo and installs `ml/requirements.txt`.
5. From here, all training code lives in `ml/`, and you `git push` results (model
   checkpoints go to Drive or cloud storage, not Git — models are too big for GitHub).

## 6b. Training environment — rented GPU (when Colab's free tier isn't enough)

Since you mentioned you can afford this: **RunPod** or **Vast.ai** are the easiest
for a hackathon budget — pick a pre-built "PyTorch" template, it comes with CUDA and
PyTorch already installed.

```bash
# once you SSH into the rented instance:
git clone https://github.com/<your-username>/trinetra.git
cd trinetra
pip install -r ml/requirements.txt
```
Then run training scripts the same way you would in Colab. Shut the instance down
when you're not actively training — you're billed per minute on both platforms.

---

## 7. Frontend (comes later, Phase 8 — skeleton included now so the folder exists)

```powershell
cd frontend
npm create vite@latest . -- --template react
npm install
npm run dev
```
We'll wire this up to the backend once the API has real endpoints to call — no
need to build this out yet.

---

## What's next

Once everything above runs (`docker ps` shows the DB, `/health` returns ok, and the
Colab notebook installs cleanly), you're done with Phase 1. Come back and we'll move
to **Phase 2: Data Acquisition** — pulling the real IMD best-track data and MOSDAC
satellite imagery into `ml/data/`.
