# Friday demo script: RouteSense proof of concept

About 6 minutes, then questions. Everything runs on your laptop; the customer step can run on Dr. Khairul's phone if you are on the same Wi-Fi (see the README).

## Before he arrives (5 minutes)

1. Start the server (README, "Run it") and open http://localhost:8000.
2. Chrome: F12, then the device toolbar (Ctrl+Shift+M), pick a phone such as Pixel 7. Zoom the page to 100%.
3. On **Today**, tap **Reset demo day**.
4. Open **Compare** once and wait until the results show (about 30 seconds). This warms the cache so it is instant during the demo. Then go back to **Today**.
5. Keep this file open on a second screen.

## The demo

### 1. The problem (30 seconds)

> "Every failed delivery is a trip the rider is not paid for, and the parcel rides again tomorrow. Route apps today find the shortest way to visit every address. RouteSense plans for the most parcels actually delivered on the first try."

### 2. Today's parcels (1 minute) — Today tab

- 16 parcels around Petaling Jaya, Damansara and Subang Jaya, from a hub in Section 13.
- Point at **May fail (expected)** and the **Ask before you go** list: each customer has a risk and a reason, for example Aisyah, a high-rise with a failed attempt before.
- Tap **Plan my day**.

### 3. The plan (1 minute) — Route tab

- Morning wave, free time, then an evening wave. Aisyah and Priya sit in the evening, tagged **Best 6:00 pm to 8:50 pm**: the model expects them to be out during office hours.
- Tap **Compare with a normal app**. The dashed line is a shortest-time planner. Read the sentence under it: the same stops, but more failed attempts expected.

### 4. The customer replies (1.5 minutes) — the key moment

- Back on **Today**, at Aisyah tap **Open customer link** (or let Dr. Khairul open the link on his phone).
- Show the page: no app, no login. Choose **Come after a time**, **After 6:30 pm**, then **Send to Hafiz**.
- Switch to the rider app. Within a few seconds a message appears: *Aisyah replied... Route updated (plan v2)*. Her risk drops from about 32% to about 7%, and her reasons now start with *Customer said: home 6:30 pm to 9:00 pm*.

> "This is the part no route app does: the customer's answer changes the plan."

### 5. On the road (1 minute) — Next stop tab

- Show **Why this risk** (the model's reasons in plain words) and **Risk through the day** (the dashed line is the planned time).
- Show the Waze and Google Maps buttons.
- Tap **Delivered**. Then on the next stop tap **Failed**, **Customer not home**: RouteSense plans a retry at a better time, or carries the parcel to tomorrow if no safer time is left.

### 6. The evidence (1 minute) — Compare tab

- Read the three red boxes: more parcels delivered today, fewer failed trips, fewer parcels left for tomorrow, against a normal route app.
- Tap **Play** under *Watch one simulated day* with **RouteSense + replies**.
- Scroll to **Under the hood**: logistic regression against XGBoost, and the three synthetic-data checks (grounded, plausible, sensitive) all passed.

## Questions he may ask

**Is the data real?**
Synthetic and seeded. Each customer has a hidden availability profile (office worker, home most of the day, out in the afternoon, business hours) that the planner never sees; outcomes are drawn from it, so the model never grades itself. The data passes the three checks from the proposal. The app already logs every real outcome, and the retraining script is built for when 300 are logged. Rider interviews will test the assumptions.

**How do the three predicted features contribute?** (assessor comment 3)
- Travel time sets the minutes for every leg, so it changes the order and the ETAs.
- Service time sets the minutes at each door (a high-rise takes longer than a landed house), so time windows stay realistic.
- Failure risk becomes a soft deadline on each stop, so risky stops move to safer hours and failed ones get a retry slot.
The experiment switches each one off in turn to measure what it adds.

**Why doesn't RouteSense without replies beat the normal app on first tries?**
An honest finding: from parcel data alone, the model cannot tell an office worker from someone who is home all day. One reply from the customer can. That is why v3 adds the reply link. The next improvement is address history (when past deliveries to that address succeeded).

**Why OR-Tools and not your own algorithm?**
It solves routing with time windows reliably, and supports the soft deadlines that carry the risk. The contribution is what goes into the solver, not the solver itself.

**What about privacy?**
Reply links carry a random code, show only the rider's first name and the arrival window, collect no location, and expire at the end of the day. The demo uses made-up names and no phone numbers.

**Why does the RouteSense day finish later?**
Customers who are out during the day get an evening slot. The time between waves is the rider's own, and it costs less than riding to doors where nobody answers and riding again tomorrow.
