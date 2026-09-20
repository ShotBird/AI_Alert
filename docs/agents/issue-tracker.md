# Issue tracker: GitHub Issues

Issues live in this repo's **GitHub Issues** (`hans10102-droid/AI_Alert`), driven with the `gh` CLI.
This is the canonical tracker: open/closed state, labels and assignment live there and nowhere else.

## History

Until 2026-09-21 this repo used a local-markdown tracker under `docs/roadmap/<feature-slug>/issues/`.
All 31 tickets were migrated to GitHub Issues on that date, in order, so **ticket number ==
issue number** (`27-news-hotness.md` is issue `#27`). The markdown files stay in the repo as the
written reasoning behind each decision — they are still worth reading and still get committed —
but they no longer carry status. The `Status:` line in each file points at its issue instead.

## Conventions

- One feature per directory for the long-form material: `docs/roadmap/<feature-slug>/`
- The spec is `docs/roadmap/<feature-slug>/spec.md`; the wayfinder map is `map.md`
- A ticket's **state** is the GitHub issue: open/closed, labels, assignee
- A ticket's **reasoning** may additionally live at
  `docs/roadmap/<feature-slug>/issues/<NN>-<slug>.md`, committed with the work it describes.
  When both exist, the issue links to the file and the file names the issue.

## Labels

Type: `type:research`, `type:task`, `type:grilling`, `type:prototype`
State beyond open/closed: `status:claimed`, `status:in-progress`, `status:open`
Triage roles (see `triage-labels.md`): `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix`

## Commands

```bash
gh issue list --state open                       # 지금 열려 있는 것
gh issue view 27                                 # 하나 읽기
gh issue create --title "..." --body-file f.md --label type:task
gh issue comment 27 --body "..."                 # 결과 기록
gh issue close 27 --reason completed
```

## When a skill says "publish to the issue tracker"

`gh issue create`. If the ticket carries long reasoning worth keeping in the repo, also write
`docs/roadmap/<feature-slug>/issues/<NN>-<slug>.md` and cross-link the two.

## When a skill says "fetch the relevant ticket"

`gh issue view <number>`. The user normally passes the number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is an issue labelled `wayfinder:map`; each ticket is an issue
linked from it. Blocking is expressed with GitHub's native "blocked by" relationship where
available, otherwise as a `Blocked by: #N` line in the body. The **frontier** is the open,
unblocked, unassigned tickets:

```bash
gh issue list --state open --search "no:assignee"
```

A session **claims** a ticket by assigning it to itself before doing any work:

```bash
gh issue edit <number> --add-assignee @me
```
