# Risks, blockers and decisions

As of 20 October 2026. Owner for project decisions: Swarneil. These are not claims that infrastructure or credentials already exist.

| ID | Risk or blocker | Impact | Treatment and observable resolution |
| --- | --- | --- | --- |
| B01 | Requested Project folder is denied to this session | Cannot place or edit the repository at the requested location | Deliver a complete archive and history bundle; extract and reopen Project/Veya as an authorized workspace |
| B02 | Native preview exits or fails to remain visible | Desktop acceptance is blocked | VEY-011 reproduces the failure, captures logs and proves a stable native launch |
| B03 | No rendered/native UI verification | Layout and interaction quality remain unknown | VEY-029, VEY-030 and VEY-214 collect actual interaction and rendering evidence |
| B04 | No live backend or inference is implemented | Current prototype cannot perform real work | R1 adds the real runtime/provider/tool path and verifies an output |
| B05 | No GitHub remote or pipeline runs | CI, protection and publication are unverified | Configure a chosen repository later; E22 requires actual run evidence |
| B06 | GPU memory and training throughput are unmeasured | Model size, sequence length and training feasibility are uncertain | VEY-161 measures dedicated VRAM and supported runtime before selecting a training configuration |
| B07 | Sandbox connector tenant and credentials are not selected | Live integration acceptance cannot run | Choose one test integration and restricted credentials before E11 live testing |
| B08 | Signing identity and GPU/cloud budget are not configured | Signed release and remote paid work cannot proceed | Record publisher credentials, one environment and explicit spending limits before executing those stages |
| R01 | Full roadmap exceeds a short solo build | Time and maintenance costs can consume the research work | Use dependency-complete release subsets; re-estimate from actual effort after ten stories |
| R02 | Too many languages and services obscure the useful contribution | More integration failure without better agent outcomes | Keep Rust host and Python core; Go/Kafka/Kubernetes expansion remains conditional |
| R03 | Fixture success does not transfer | Results may overstate usefulness | Preserve realistic hidden-state environments, held-out families and external sandbox tests |
| R04 | Reward shortcuts or judge bias | Training optimizes the wrong behavior | Exploit tests, verifiable outcomes, human calibration, paired comparisons and negative-result retention |
| R05 | Context or memory crosses tenant boundaries | Data disclosure or inappropriate actions | Enforce scope before retrieval/use and test all API, cache, memory and export surfaces |
| R06 | Timeout after a remote write | Duplicate business effects | Persist intent before the call; reconcile operation identity before retry |
| R07 | Imported skills contain unsuitable examples or numeric claims | Incorrect code or unjustified thresholds | Apply the qualifications in ENGINEERING_STANDARD.md and verify current primary documentation |
| R08 | Tracking becomes a second source of false completion | Misleading delivery status | Require a real code commit, local evidence and a separate integration-acceptance record |
| R09 | Source or model license limits redistribution | Public releases may contain unsuitable artifacts | Retain provenance, review licenses and download model weights separately unless redistribution is permitted |

## Decisions before costly work

| Decision | Current working choice | Trigger for finalizing |
| --- | --- | --- |
| Public product name | Veya, provisional | Before registering domains, publishing packages or using a public brand |
| Personal hardware | RTX 4050; dedicated VRAM unconfirmed | Before selecting model/training recipes |
| First inference mode | User-configured local endpoint | Before VEY-042 acceptance; record model revision and measured limits |
| Hosted fallback | One provider, only with permitted data egress | Before VEY-043 and VEY-050 acceptance |
| Local orchestration | Checkpointed Python loop and SQLite | R1; Temporal belongs to server-owned durable execution |
| First external integration | One sandbox drive or ticket tenant | Before VEY-104/105 live contract tests |
| Remote infrastructure | One environment only if needed | Before E21 optional infrastructure deployment |
| Post-training | LoRA SFT first; DPO after pair quality | After the evaluation baseline and approved dataset exist |
| Reinforcement learning | Optional GRPO experiment | Only after verifiable reward and exploit gates pass |
| GitHub tracking authority | Local ledger until explicit migration | When remote issues and reconciliation are actually implemented |

## Change-control rule

Record significant scope, architecture and acceptance changes in Git with their reason. Do not silently reinterpret a blocked or failed requirement as complete. No retrospective change to the held-out evaluation or success criterion may be used to claim the original experiment succeeded.
