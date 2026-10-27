# 🃏 KEMS ARENA 🐾

A fun, multimodal card game where **Le Chonk** (`mistral-large-4`) plays **Kems** — the classic 2 vs 2 game of secret signals, social deduction, and card table banter.

---

## 🌟 Overview

**Kems Arena** lets AI players team up around a retro poker table to play Kems:

1. **Vision at the Table**: Le Chonk visually inspects procedural card table frames rendered on the fly before picking card exchanges.
2. **Secret Team Signals**: Teammates whisper in private before the match to agree on a coded phrase (*"purrfect"*, subtle phrasing, emoji tells).
3. **Public Chat & Camouflage**: Players chat publicly around the felt, slipping in their secret signal without tipping off the other team.
4. **KEMS! or COUNTER!**: Once a player gathers 4 of a kind (a square), their partner must spot the trigger and shout **`KEMS!`** before opponents call **`COUNTER!`**.

```
       [ Team 0 ]                                [ Team 1 ]
        P1 & P4                                   P2 & P3
           \                                         /
            ▼                                       ▼
  ┌────────────────────────────────────────────────────────┐
  │                 🃏 KEMS ARENA POKER TABLE 🃏            │
  │  [Center Pool]  4♠  7♥  10♦  2♣ (swappable cards)     │
  │  [Public Chat]  "Nice spread on the felt today..."     │
  │  [Private CoT]  "Partner sent the trigger! CALL KEMS!" │
  └────────────────────────────────────────────────────────┘
```

---

## 🚀 Quickstart

### 1. Installation

Requires Python 3.10+.

```bash
# Clone the repository
git clone https://github.com/axiome02/le-chonk-kems.git
cd le-chonk-kems

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Set your Mistral API key in a `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
MISTRAL_API_KEY=your_mistral_api_key_here
```

### 3. Run the Game

#### Option A: Web Dashboard (Recommended)

Start the local server and automatically open the interactive card table dashboard in your browser:

```bash
python run_chonk.py
```

Or run via the module CLI:
```bash
python -m kems.run --serve
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** to:
- Watch cards swap dynamically on the table.
- Read secret team negotiations, private Chain-of-Thought logs, and public banter.
- Step through match replays with the built-in timeline.

#### Option B: Terminal Live Play

Run a match directly in your terminal:

```bash
python -m kems.run --live
```

Add `--vision` to let models visually inspect the table:
```bash
python -m kems.run --vision --live
```

---

## 🛠️ CLI Reference

```bash
python -m kems.run [OPTIONS]

Options:
  --model TEXT       Model identifier (default: mistral-large-4)
  --vision           Enable multimodal table rendering via Pillow
  --seed INT         Random seed for card deal and turn order (default: 42)
  --ranks INT        Number of card ranks in deck (1..N, default: 10)
  --max-rounds INT   Maximum rounds per match
  --max-turns INT    Maximum turns per round (default: 8)
  --live             Stream public dialogue and moves in terminal
  --serve            Launch local web dashboard server
  --demo             Run pre-recorded demo match without API calls
  --port INT         Dashboard port (default: 8000)
  --pause FLOAT      Pause between API calls (default: 0.5s)
```

---

## 🧪 Testing

The test suite runs 100% locally and deterministically without requiring an API key:

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
