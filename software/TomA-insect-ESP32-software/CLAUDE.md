# Project notes for Claude

## Publishing model: this repo has no remote, by design

This local repo (`master` branch) is **not** connected to any GitHub remote —
`git remote -v` here is intentionally empty. Do not read that as "nothing has
been pushed." It means publishing is a deliberate, separate step, not a plain
`git push`.

The real upstream is a shared monorepo:

- **Upstream repo:** `https://github.com/InsectAI-COST-Action/kit-for-kids` (MIT licensed), branch `main`.
- **This project lives there at:** `software/TomA-insect-ESP32-software`, imported as a **git subtree** (not a submodule) so its full commit history was preserved on import rather than starting fresh.
- **Publishing station:** a separate, ordinary clone of `kit-for-kids` at `C:\k4k\kit-for-kids` (`/c/k4k/kit-for-kids` from Git Bash). It exists solely to run subtree commands against; nobody edits files there directly.

### To publish local commits made in this repo

Run from **Git Bash** (path handling below assumes POSIX-style paths; see the
Git Bash caveat in [docs/dev-bridge.md](docs/dev-bridge.md) if adapting for
PowerShell):

```bash
cd /c/k4k/kit-for-kids
git pull --quiet --no-edit
git subtree pull --prefix=software/TomA-insect-ESP32-software \
  "/g/My Drive/InsectAI - Core Group/WG 2/2027_DesignHack_kit4kids/Subgroup - enclosure/pilot camera software system" master \
  --squash -m "Update camera software: <short description>"
git push origin main
```

`--squash` keeps the monorepo's history to one commit per publish rather than
importing every local commit individually — that's a deliberate choice made
after the initial import (which *did* bring the full pre-existing history
across once, on purpose; see rationale below).

**Check what's actually published** by comparing `git log --oneline -1` in
this repo against the subtree-pull commit messages in `C:\k4k\kit-for-kids`'s
log (`cd /c/k4k/kit-for-kids && git log --oneline -5`) — a commit made here is
invisible on GitHub until the publish step above has been run for it.

A `publish.ps1` wrapper to reduce the risk of mistyping this command was
proposed but never built — worth doing if this becomes routine.

### Why a subtree instead of a plain remote or submodule

Established 27 August 2026, when this project was first connected to
`kit-for-kids`: a plain copy into the monorepo would have lost this project's
own commit history, and this project's local `.git` metadata had corruption
history it needed to disclose/avoid carrying over uncritically (later
identified as recurring `desktop.ini` pollution — see below). `git subtree
add` was used once to bring the existing history in under the target path
without altering how this local repo works day-to-day; `git subtree pull
--squash` is the steady-state update path.

At import time: a directory had already been *manually* copied into
`kit-for-kids` at the same path by hand (losing history) — that was removed
in a clearly-labelled commit before the subtree import so nothing was lost
silently. Verified before the first push: no secrets in any of the ~40
commits of history; the monorepo's own root README/LICENSE untouched; local-
only heavy directories (`datasets/`, `spikes/`, `artifacts/`, `archive/`, ≈700
MB) correctly stayed out of what got published.

### What never gets published

Everything `.gitignore` excludes locally stays local — the subtree pull only
ever sees this repo's own tracked, committed content. In particular
`archive/` and `datasets/ant-example-images/` were added to `.gitignore` on
27 August 2026 and were never published in the first place.

## Known infra gotcha: this repo's `.git` lives inside Google Drive sync

The whole project folder (including `.git`) is inside a Google Drive–synced
directory (`G:\My Drive\...`). Drive/Explorer periodically drops `desktop.ini`
into every folder it touches, including deep inside `.git/refs` — and a
second tool (Codex CLI) also uses this repo and creates large nested ref
trees (`refs/codex/turn-diffs/...`), multiplying the exposure. On 27 August
2026 this had accumulated to **694** stray `desktop.ini` files under `.git`,
which broke `git branch -a`, `git fsck`, and a background `pack-refs` task
(visible as `fatal: bad object refs/agents/desktop.ini` and a stale
`packed-refs.lock` during an otherwise-successful commit).

**Fix if it recurs:** `find .git -iname "desktop.ini" -delete`, then confirm
with `git fsck --no-progress` (only harmless `dangling blob` lines should
remain) and `git status`. The same sync/multi-tool combination also produces
stale `*.lock` files directly under `.git/refs/codex/...` (8 found and
cleared on 27 August 2026, alongside the 694 `desktop.ini` files) — check
first that no Codex process is actually running, then
`find .git/refs -iname "*.lock" -delete` is safe. This is a symptom-level
fix, not a root-cause one — the root cause (git internals inside a
cloud-sync folder, shared with another tool's own ref namespace) hasn't been
addressed and could in principle cause worse corruption than clutter; no
incident of that kind has occurred yet.
