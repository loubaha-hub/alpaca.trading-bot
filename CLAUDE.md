# Alpaca trading bot - read this first

This file loads automatically at the start of every Claude Code session in this
repository. Before doing anything else, also read:

- `memory/now.md` - where things stand right now: the working branch, what is
  live, what is waiting on the owner, the next steps.
- `memory/journal.md` - decisions, instructions and results worth keeping,
  newest first.
- `memory/playbook.md` - how the owner traded by hand, profitably. The bot
  is meant to follow it.

THIS REPOSITORY IS PUBLIC. Never write keys, secrets, passwords or account
numbers into any file here - memory files included.

## Standing rules from the owner

- **Nothing goes to `main` without the owner's explicit OK.** Render deploys
  every commit to `main`, and a deploy restarts the bot, which wipes its watch
  list and per-symbol state. Restart only when all three accounts are flat, or
  after hours (after 8pm ET). Work on the branch named in `memory/now.md`.
- Never ask for keys or secrets in the chat; the owner types them only into
  settings screens. Do not regenerate Alpaca keys.
- Claude's access to Alpaca is read-only unless the owner explicitly says
  otherwise. Never approve Webull order tools ("place ... instruction",
  "revoke instruction").
- `watchman.py` stays off `main` until the real-money account opens.
- Accounts are identified by number, not by the names Alpaca shows. The
  account ending **T6HH** runs v31 (the workhorse), **P28T** runs v34,
  **AUES** runs v35. v32 stays off.
- Judging a change: all the days, never one stock. Show the gains and the
  costs and the trade counts, test on days that were not used to design it,
  check it holds across a range of settings, and give a market reason.
  **Live results outrank replays.**
- Premarket (4:00-9:30 ET) is prime time and gets its own design; regular
  hours (9:30-4:00, with LULD halts) get a separate one.
- The no-chase rule stays. Work on the leash and on re-entry instead.

## Memory

- When the owner says "remember", "memorize", "save this" or "note this",
  use the `/remember` skill (`.claude/skills/remember/SKILL.md`): a short dated
  entry in `memory/journal.md`, committed and pushed to the working branch.
- At the end of a block of work, bring `memory/now.md` up to date.
- Record a decision as a decision only when the owner made it; otherwise it
  is a proposal.

## Where things are

- `r34.py` - the live bot: v31 is the base class, V34 and V35 subclass it.
  One process, one Alpaca SIP data connection shared by the strategies.
- `replay/replay.py` - replays recorded 1-minute bars through the bot's code.
  Its fills and spreads are invented, and kinder than the live market (see the
  journal, 2026-10-05). `replay/data/` holds the recorded bars; `replay/out/`
  is not kept in git; `replay/live/` holds live log lines saved from Render.
- `tests/` - `cd tests && python -m pytest -q`.
- Render keeps the bot's logs for about 7 days only - save what matters.
