# BusyBrain Multi-Agent Planner

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

BusyBrain turns an overwhelming week into a humane plan. Instead of producing a
generic to-do list, one public orchestrator coordinates three independently
registered Fetch.ai uAgents that reason about study workload, calendar logistics,
and sustainable pacing. The final answer includes the invisible work that ordinary
calendars miss: setup, travel, food, transitions, breaks, and recovery.

## Why agents?

The specialists have intentionally different goals. The Study Planner protects
learning progress, the Calendar Planner protects time constraints, and the Wellness
Planner protects the student's capacity. The orchestrator must reconcile their
recommendations into one usable plan. This makes agent coordination central to the
product rather than an eligibility wrapper around a chatbot.

## Agent network

| Agent | Responsibility | Port | Address |
|---|---|---:|---|
| [BusyBrain Orchestrator](https://agentverse.ai/agents/details/agent1q2qrnqd6v20qx0ltq2pnt2r85fadkekgs2js07w84h9jj87lhgm2crewv4j/profile) | ASI:One Chat Protocol entry point and final synthesis | 8001 | `agent1q2qrnqd6v20qx0ltq2pnt2r85fadkekgs2js07w84h9jj87lhgm2crewv4j` |
| [Study Planner](https://agentverse.ai/agents/details/agent1qdchqqjrvhyvx9cxxtmgwy498zwscn9ac9yqja43cqv90w3q3asq70rjrww/profile) | Focus rhythms, workload, deadlines, and daily study limits | 8002 | `agent1qdchqqjrvhyvx9cxxtmgwy498zwscn9ac9yqja43cqv90w3q3asq70rjrww` |
| [Calendar Planner](https://agentverse.ai/agents/details/agent1qvv9585yydz2r9p3n245t9y6l46kqpsa0e299n93nl5y60f6lgfwx64wygz/profile) | Fixed events, conflicts, travel, preparation, and transitions | 8003 | `agent1qvv9585yydz2r9p3n245t9y6l46kqpsa0e299n93nl5y60f6lgfwx64wygz` |
| [Workload & Social Context](https://agentverse.ai/agents/details/agent1q0pkvdgsxv4w8r5lqh2chmlhantxtlk28e5yh9g06ah5xwnuvqznqzenkwe/profile) | Calendar-pressure signals, fair meetup timing, recovery, and rationale | 8004 | `agent1q0pkvdgsxv4w8r5lqh2chmlhantxtlk28e5yh9g06ah5xwnuvqznqzenkwe` |

## End-to-end flow

1. A user sends a natural-language request from ASI:One.
2. BusyBrain acknowledges the Chat Protocol message and creates a request ID.
3. It dispatches a typed `PlanningRequest` to the Study, Calendar, and Workload & Social specialists.
4. Each specialist returns a signed `SpecialistResponse`.
5. BusyBrain verifies each sender, waits for all three, resolves conflicts, and
   returns ranked options through the Chat Protocol.
6. The user replies `choose option 1`, `choose option 2`, or `choose option 3`.
7. BusyBrain persists a confirmed-event action receipt and returns a populated
   Google Calendar action link—all inside the ASI:One conversation.

If a specialist is unavailable, the orchestrator finalizes after 45 seconds with
the verified partial results and names the missing specialist instead of hanging.

## Local setup

Python 3.12 or 3.13 is recommended.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add an ASI:One key and four unique private seeds to `.env`. Never commit `.env`;
changing a seed after registration changes that agent's address.

Run each agent in its own terminal:

```bash
make orchestrator
make study
make calendar
make workload
```

Open each Inspector URL, choose **Connect → Mailbox**, and keep all four processes
running for the live demo. Each agent needs its own mailbox.

Before testing in ASI:One, validate the exact same Chat Protocol route locally in a
fifth terminal:

```bash
make smoke-test
```

The client prints `TEST PASSED` after the orchestrator has collected all three
specialist responses and returned the final plan. Press Ctrl+C after the result.

## ASI:One demo prompt

> Find me 45 minutes with Maya in the next seven days, preferably in the afternoon
> and not right after class. Compare both calendars, give me the three best options,
> and explain why the top time is fair to both of us.

Then reply:

> choose option 2

The terminal logs show the orchestrator dispatching the request and receiving three
specialist responses before returning the synthesized plan. The Workload & Social
agent calls the deterministic ranking engine against seeded calendars, so the times
and fit scores are evidence rather than invented availability. The second turn
produces a durable confirmation receipt and a Google Calendar action.

## Pika invitation handoff

After the user approves a meetup time, the Streamlit experience prepares a
consent-gated Pika invitation using a saved cartoon avatar rather than a real
person's face. The creative concept turns her wrist calendar into a glowing
jellyfish portal whose bubbles assemble into the confirmed date, time, and place.

The Pika MCP workflow is deliberately multi-step: generate a short spoken invitation,
animate the approved avatar to that audio, and render the confirmed event details as
stable mobile-safe text. The output is an 8-second vertical clip displayed beside the
calendar confirmation. Scheduling remains independent, so a media-provider delay can
never lose or invalidate the confirmed event. This combines an original visual story,
privacy-aware generation, and a shareable action outcome instead of treating video as
decoration.

## Existing product prototype

The repository also contains a Streamlit interface and deterministic scheduling
engine:

```bash
streamlit run app.py
python main.py
```

These modules demonstrate the broader product direction; the Agentverse workflow is
implemented by `agent.py`, `study_agent.py`, `calendar_agent.py`, and
`wellness_agent.py`.

For the complete browser demo (calendar UI + interactive Pika message), run:

```bash
.venv/bin/uvicorn api:app --reload --port 8000
python3 -m http.server 8080
```

Then open `http://localhost:8080/`. Keep both processes running during the demo.

To start the website, API, and all four Fetch.ai agents from one terminal instead:

```bash
make app
```

Press `Ctrl+C` once to stop every Busy Brain process.

## Safety and scope

BusyBrain provides planning support, not medical diagnosis, therapy, or professional
academic advice. Specialist responses are treated as recommendations, and missing
schedule information is surfaced as an assumption rather than silently invented.

## Hackathon submission checklist

- [ ] Public GitHub repository
- [x] Four Agentverse profile links documented
- [ ] Shared ASI:One chat session
- [ ] Three-to-five-minute demo video
- [ ] Devpost explanation and architecture

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers natural-language constraints, collision prevention, recovery-gap
ranking, option selection, durable confirmation, and Google Calendar handoff URLs.
