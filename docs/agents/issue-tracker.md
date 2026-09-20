# Issue tracker: Local Markdown (committed)

Issues and specs for this repo live as markdown files under `docs/spd-roadmap/`, committed to git alongside the code. There is no external tracker; `gh`/`glab` are not used.

## Conventions

- One feature per directory: `docs/spd-roadmap/<feature-slug>/`
- The spec is `docs/spd-roadmap/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `docs/spd-roadmap/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading
- Every issue/spec change is committed to git together with the work it describes

## When a skill says "publish to the issue tracker"

Create a new file under `docs/spd-roadmap/<feature-slug>/` (creating the directory if needed), then commit it.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `docs/spd-roadmap/<effort>/map.md` (the Destination / Notes / Decisions-so-far / Not-yet-specified / Out-of-scope body).
- **Child ticket**: `docs/spd-roadmap/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `docs/spd-roadmap/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
