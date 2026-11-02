# RouteSense

Failure-aware delivery planning for Malaysian parcel riders. Final year project, Bachelor of Computer Science, Universiti Putra Malaysia.

Route apps today find the shortest way to visit every address. RouteSense plans for the most parcels actually delivered on the first try: it predicts which deliveries are likely to fail, asks those customers on WhatsApp before the rider goes, and re-plans by itself after every delivery, failure or reply.

This repository is the **proof of concept**: a working rider app, a customer reply page, the planning engine, the failure-risk model, and a simulator that compares RouteSense with a normal route app.

## What you can do with it

- **Rider app (phone-sized web app):** see today's 16 parcels with a failure risk and plain-language reasons for each, plan the day, open the next stop in Waze or Google Maps, and mark each stop delivered or failed. The plan updates after every outcome.
- **Customer link:** no app and no login. The customer picks *I'll be home*, *come after* or *before a time*, *leave it with the guard*, *cash is ready*, *tomorrow* or *self-collect*. The rider's route changes within seconds.
- **Compare:** the same day played by four strategies (the rider's usual way, a normal route app, RouteSense, RouteSense with customer replies), with outcomes drawn from hidden customer profiles the planner never sees.

## Run it

You need **Python 3.11, 3.12 or 3.13** and **Git**. Node.js is only needed if you change the app's screens.

### Windows (PowerShell)

```powershell
git clone https://github.com/NanoFGX/RouteSense.git
cd RouteSense\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn routesense.api:app --port 8000
```

If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

### macOS or Linux

```bash
git clone https://github.com/NanoFGX/RouteSense.git
cd RouteSense/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn routesense.api:app --port 8000
```

Then open **http://localhost:8000**. For a phone-sized view in Chrome, press F12 and turn on the device toolbar (Ctrl+Shift+M). The API's own documentation is at http://localhost:8000/docs.

The first start trains nothing (the model is already in `backend/models`) and warms the Compare screen in the background, which takes about 30 seconds.

### Show it on your phone

Both devices must be on the same Wi-Fi. Campus Wi-Fi often blocks device-to-device traffic, so a phone hotspot is the safest choice.

1. Find the laptop's address. Windows: `ipconfig`, the IPv4 Address, for example `192.168.1.23`.
2. Tell RouteSense that address, so customer links point to the laptop, then start it for the network:
   ```powershell
   $env:ROUTESENSE_PUBLIC_URL = "http://192.168.1.23:8000"     # macOS/Linux: export ROUTESENSE_PUBLIC_URL=http://192.168.1.23:8000
   python -m uvicorn routesense.api:app --host 0.0.0.0 --port 8000
   ```
3. On the phone, open `http://192.168.1.23:8000`. Allow Python through the Windows firewall if it asks.

## The demo

[docs/demo-script.md](docs/demo-script.md) is a six-minute walkthrough for the supervisor, with answers to the questions most likely to come up.

## How it works

```
Rider app ─┐                         ┌─ Travel time   (estimate now, Google Routes API next)
Customer ──┼─ FastAPI ─ Planner ─────┼─ Service time  (minutes at the door, by property type)
link       │            (OR-Tools)   └─ Failure risk  (XGBoost + reasons, updated by replies)
Simulator ─┘                │
                         SQLite (day state + every outcome logged for retraining)
```

| Part | File | What it does |
| --- | --- | --- |
| Planner | `backend/routesense/planner.py` | OR-Tools routing with time windows. Failure risk becomes a soft deadline on each stop, so risky stops move to the hours when the customer is likely in. Also the two baselines: nearest next stop, and a shortest-time planner like a normal route app. |
| Failure-risk model | `backend/routesense/risk/` | Synthetic ground truth, training (logistic regression against XGBoost, split by route), plain-language reasons from TreeSHAP, and the update from customer replies and failed attempts. |
| Simulator | `backend/routesense/simulator.py` | Replays a day: legs run a little slower than planned, and every attempt succeeds or fails according to the hidden customer profile. |
| API | `backend/routesense/api.py` | `/api/plan`, `/api/outcome`, `/api/reply/{token}`, `/api/simulate`, `/api/compare`, `/api/model`, and more. Also serves the built app. |
| App | `frontend/` | React, TypeScript, Tailwind CSS and Leaflet. The built copy in `frontend/dist` is what the backend serves. |
| Settings | `backend/routesense/config.py` | Every assumption in one place: service times, speeds, the cost of a failed trip, reply effects, retry rules. |

## Useful commands

Run these from `backend` with the virtual environment active.

| Command | What it does |
| --- | --- |
| `python -m pytest -q` | Runs the 14 tests (planner, model, API and simulator). |
| `python -m routesense.risk.train` | Regenerates the synthetic data, runs the three data checks and retrains the model. |
| `python -m routesense.experiment` | Quick experiment: 10 random days × 5 replays × 4 strategies, saved to `backend/results/experiment.csv`. |
| `python -m routesense.experiment --days 30 --replays 30` | The full design from the proposal (about 2 hours). |

To change the screens: `cd frontend`, `npm install`, `npm run dev` (opens http://localhost:5173 and talks to the backend on port 8000), then `npm run build` so the backend serves the new version.

## Preliminary results

From the quick experiment (`python -m routesense.experiment`): 10 random Klang Valley days of 15 parcels, each replayed 5 times per strategy with the same random draws, the 25% failure scenario, and 60% of customers replying.

| Strategy | Delivered today | On the first try | Failed trips | Left for tomorrow | Unpaid minutes | Km |
| --- | --- | --- | --- | --- | --- | --- |
| Rider's usual way (nearest next stop) | 10.30 | 10.30 | 4.20 | 4.70 | 58.8 | 44.4 |
| Normal route app (shortest time) | 10.86 | 10.86 | 4.14 | 4.14 | 55.3 | 44.4 |
| RouteSense, no replies | 12.14 | 11.02 | 5.46 | 2.86 | 80.1 | 57.4 |
| **RouteSense with replies** | **13.52** | **12.40** | **2.66** | **1.48** | **36.4** | 52.8 |

Against a normal route app, RouteSense with replies delivered 2.7 more parcels a day (paired Wilcoxon, p = 2e-9) and cut failed trips from 4.1 to 2.7 (p = 5e-6), at the cost of about 8 more kilometres and an evening wave. Without replies, RouteSense delivered more through same-day retries but made more failed trips (p = 1e-4): from parcel data alone the model cannot tell who is home, which is exactly what the customer link fixes. These are simulated results on synthetic data; the assumptions are listed below.

## What is real and what is assumed

- **Working:** the OR-Tools planner, the model pipeline (data checks, training, evaluation, reasons), the API, the rider app, the customer reply loop, outcome logging, and the simulator.
- **Assumed, stated in `config.py` and `risk/synth.py`:** customer availability profiles, failure probabilities, service times, travel speeds by hour (until a Google Routes API key is added), reply rates and how much a reply changes the risk.
- **Not built yet:** the Google Routes API provider, team mode, prayer-time and weather rules, the Bahasa Melayu interface, and a public deployment.

## Next steps after the proof of concept

1. Google Routes API travel times (traffic-aware matrices, cached, with a monthly budget guard), keeping the estimate as the fallback.
2. Address history as a model feature, so RouteSense can time stops well even before customers reply.
3. Prayer breaks (JAKIM e-Solat zones) and MET Malaysia storm warnings in the planner.
4. Team mode: split one day's parcels fairly across 2 to 10 riders.
5. Bahasa Melayu interface, the full 30 × 30 experiment, rider interviews and the usability test.
