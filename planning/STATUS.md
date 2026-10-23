# Veya delivery status

Canonical source: `planning/backlog.json`. This report is regenerated after every tracker update. Story counts reflect accepted implementation evidence, not planning effort.

**Build progress: 10/240 stories done.** Ready to start: 8.

| Status | Stories |
| --- | ---: |
| backlog | 230 |
| blocked | 0 |
| done | 10 |
| in_progress | 0 |
| in_review | 0 |

## Release scope and effort

Release scopes are cumulative through dependencies where applicable; do not add their totals together. Hours are uncalibrated estimates, not measured productivity or promised dates. Each scope includes its full prerequisite closure.

| Release | Stories | Done | Base hours | Range hours | Base with 25% integration allowance | Weeks at 15 h/week |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| R0: Native recovery checkpoint | 3 | 1 | 17 | 12-26 | 22 | 2 |
| R1: First real delegated task | 35 | 9 | 211 | 143-321 | 264 | 18 |
| R2: Invoice MVP | 63 | 9 | 392 | 269-596 | 490 | 33 |
| R3: Evaluation and learning beta | 122 | 9 | 786 | 540-1197 | 983 | 66 |
| R4: Operational desktop release | 220 | 10 | 1447 | 1005-2201 | 1809 | 121 |
| R5: Full optional research roadmap | 240 | 10 | 1633 | 1139-2480 | 2042 | 137 |

## Ready queue

| Story | Code change | Base hours |
| --- | --- | ---: |
| VEY-002 | Apply the Veya application identity | 3 |
| VEY-003 | Lock supported toolchains | 3 |
| VEY-057 | Implement intent-based idempotency | 8 |
| VEY-041 | Define provider capabilities and configuration | 4 |
| VEY-051 | Create the typed tool registry | 5 |
| VEY-040 | Build workspace backup and restore | 7 |
| VEY-064 | Build tamper-evident audit records | 7 |
| VEY-091 | Add the Temporal worker deployment | 6 |

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

- 2026-10-23T00:12:45+00:00: VEY-035 in_review -> done
- 2026-10-23T00:12:46+00:00: VEY-036 backlog -> in_progress
- 2026-10-23T00:15:13+00:00: VEY-036 in_progress -> in_review
- 2026-10-23T00:15:14+00:00: VEY-036 in_review -> done
- 2026-10-23T00:15:14+00:00: VEY-037 backlog -> in_progress
- 2026-10-23T00:17:38+00:00: VEY-037 in_progress -> in_review
- 2026-10-23T00:17:38+00:00: VEY-037 in_review -> done
- 2026-10-23T00:17:38+00:00: VEY-038 backlog -> in_progress
- 2026-10-23T00:20:20+00:00: VEY-038 in_progress -> in_review
- 2026-10-23T00:20:21+00:00: VEY-038 in_review -> done
