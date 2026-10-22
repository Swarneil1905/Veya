# Veya delivery status

Canonical source: `planning/backlog.json`. This report is regenerated after every tracker update. Story counts reflect accepted implementation evidence, not planning effort.

**Build progress: 1/240 stories done.** Ready to start: 4.

| Status | Stories |
| --- | ---: |
| backlog | 239 |
| blocked | 0 |
| done | 1 |
| in_progress | 0 |
| in_review | 0 |

## Release scope and effort

Release scopes are cumulative through dependencies where applicable; do not add their totals together. Hours are uncalibrated estimates, not measured productivity or promised dates. Each scope includes its full prerequisite closure.

| Release | Stories | Done | Base hours | Range hours | Base with 25% integration allowance | Weeks at 15 h/week |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| R0: Native recovery checkpoint | 3 | 1 | 17 | 12-26 | 22 | 2 |
| R1: First real delegated task | 35 | 1 | 211 | 143-321 | 264 | 18 |
| R2: Invoice MVP | 63 | 1 | 392 | 269-596 | 490 | 33 |
| R3: Evaluation and learning beta | 122 | 1 | 786 | 540-1197 | 983 | 66 |
| R4: Operational desktop release | 220 | 1 | 1447 | 1005-2201 | 1809 | 121 |
| R5: Full optional research roadmap | 240 | 1 | 1633 | 1139-2480 | 2042 | 137 |

## Ready queue

| Story | Code change | Base hours |
| --- | --- | ---: |
| VEY-002 | Apply the Veya application identity | 3 |
| VEY-003 | Lock supported toolchains | 3 |
| VEY-004 | Add validated runtime configuration | 4 |
| VEY-031 | Define task and run domain contracts | 5 |

## Planning deliverables

| ID | Deliverable | Status | File |
| --- | --- | --- | --- |
| P01 | Comprehensive scope and goals | delivered | `planning/SCOPE.md` |
| P02 | 240 code-change stories | delivered | `planning/BACKLOG.md` |
| P03 | Milestones and deliverable register | delivered | `planning/DELIVERABLES.md` |
| P04 | Persistent status tracker and update tool | delivered | `scripts/project.py` |
| P05 | Risks, decisions and release strategy | delivered | `planning/RISKS.md` |
| P06 | GitHub-ready issue payloads | delivered | `planning/github-issues.json` |

## Active blockers

See RISKS.md. The requested Project folder is not writable from this session; the existing native preview failed its launch attempt; live backend, credentials and GitHub execution remain unimplemented or unconfigured.

## Recent tracker events

- 2026-10-22T00:19:20+00:00: VEY-001 backlog -> in_progress
- 2026-10-22T00:23:40+00:00: VEY-001 in_progress -> in_review
- 2026-10-22T00:23:41+00:00: VEY-001 in_review -> done
