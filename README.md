# PacMan Backend + React Frontend

## Architecture

- `game.py`: simulation engine + API backend
- `frontend/`: React UI (Vite)

The React app receives `maze_layout` JSON from the Python backend and controls the simulation using `continue` / `quit` signals.

## Requirements

- Python 3.10+ (tested with Python 3.13)
- Node.js 18+ and npm

## New Device Setup

From project root:

```powershell
git clone <your-repo-url>
cd PacMan
```

### 1) Install Python dependencies

Create and activate a virtual environment, then install backend packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `python` does not work on Windows, use `py` instead:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

### 2) Install Node dependencies

```powershell
cd frontend
npm ci
cd ..
```

## Run The App

From project root:

```powershell
python game.py --api --host 127.0.0.1 --port 5000
```

Open a second terminal:

```powershell
cd frontend
npm run dev
```

Then open:

- `http://127.0.0.1:5173`

## API Endpoints

- `GET /api/state`: current simulation snapshot including `maze_layout`
- `POST /api/start`: resets game (optional JSON config)
- `POST /api/signal`: `{ "action": "continue" }` or `{ "action": "quit" }`

## Optional Start Config Payload

`POST /api/start`

```json
{
  "minimax_depth": 4,
  "ghost_mcts_depth": 8,
  "ghost_mcts_iterations": 200
}
```
