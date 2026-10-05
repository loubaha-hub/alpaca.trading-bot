---
name: remember
description: Save something the owner wants kept across sessions - a decision, an instruction, a result, an improvement - into the project's memory (memory/journal.md, and CLAUDE.md for standing rules), then commit and push it to the working branch. Use when the owner says "remember", "memorize", "save this", "note this" or "keep this", or types /remember.
---

# Remember

The owner's memory for this project lives in the repository, so it survives
the end of a session. CLAUDE.md loads at the start of every session and points
to `memory/now.md` and `memory/journal.md`.

THE REPOSITORY IS PUBLIC. Never save keys, secrets, passwords or account
numbers. Accounts are named by the last four characters of their number.

1. **What to save.** What the owner named in the arguments, or the point just
   discussed. If it is unclear which point they mean, ask in one line.
2. **The journal entry.** At the top of `memory/journal.md`, under today's ET
   date heading (add it if missing, newest first), write a `###` heading of a
   few words and 1-6 bullets of plain facts: what was decided or found, the
   numbers, why, and where it lives (file, commit, switch name). Write a
   decision as a decision only if the owner made it; otherwise call it a
   proposal. Short - this is a record, not a report.
3. **A standing rule** ("always", "never", "from now on"): also add it to
   "Standing rules from the owner" in `CLAUDE.md`.
4. **Where things stand.** If it changes what is live, what is waiting or what
   comes next, update `memory/now.md` and its date line.
5. **Save it.** Commit only those files, with the message
   `memory: <the heading>`, and push to the working branch named in
   `memory/now.md` (retry a failed push up to 4 times, waiting 2, 4, 8, 16s).
   Never push to `main`: a commit there restarts the live bot. Memory reaches
   `main` with the next release the owner approves.
6. **Confirm** in one line what was saved and where.
