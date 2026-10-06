# Where things stand

Updated 2026-10-05, evening ET.

## Code
- Working branch: `claude/zealous-ramanujan-br3gay` (from 2026-10-05 evening;
  `claude/kind-goldberg-8ue38f` is merged into it). New work goes here;
  nothing goes to `main` without the owner's OK.
- Live on `main` (Render): VERSION v31-r34.3 - v31, v34, v35 on paper; the
  earn rule on for v31 and v34 (top 1, all day).
- On the branch only, all off: the owner's earn-rule switches, the 9:30
  cutoff, `replay.py --slip-pct`, `watchman.py` (until the real-money account).
- Release builds are made in a separate git worktree, never by switching
  branches in the main checkout while replays run.

## Waiting on the owner
1. Environment settings for Alpaca tick data (network + key; see the journal).
2. Whether to freeze rule changes, ship the 9:30 cutoff, halve position size,
   or run the older version on one account side by side.
3. OK to bring this memory (CLAUDE.md, memory/, the /remember skill) to
   `main` with the next after-hours release, so every new session loads it.

## Next steps
- 2026-10-06: the owner's playbook is in memory/playbook.md and as numbers in
  memory/rules.md (draft 1, numbers marked (?) to confirm). Built on the
  branch: the fast buy reload (7be5a47). Next: the owner corrects the rule
  sheet, then build the playbook strategy on one account.
0. Waiting on the owner (10-05 evening): read their Webull order history
   (read-only) to compare their trades with the bot's; what to do with the
   bots tomorrow (pause, smaller size, or as is); their walkthrough.
   Fixable on the branch, not shipped: the buy overfill (see the journal).
1. Keep the past week's live log lines (`replay/live/`) in the project.
2. With tick data: replay the six days print by print, then compare each live
   trade with the replay - the bot's execution vs what the market did.
3. Line up each account's daily live results against the date of every change.
4. Later: premarket design (entry price on fast names, sizing on proven
   runners, an adaptive leash), regular-hours design, a guard against two
   instances overlapping during a deploy, the 9:30 tick-queue overflow.
