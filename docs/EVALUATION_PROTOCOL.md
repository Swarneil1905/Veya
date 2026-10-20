# Evaluation and learning protocol

This is a proposed protocol, not a completed experiment. All UI report numbers are fictional. Passing deterministic prototype tests is not model-quality evidence.

## Primary hypothesis

A bounded intervention selector improves end-to-end task success per dollar over a fixed harness while preserving critical policy invariants. It chooses among retrieval repair, clarification, verification, tool reconciliation, reviewed memory, and stronger-model escalation. Permission enforcement remains outside the learned selector.

Start with rules derived from failure analysis. Compare to a learned ranker/contextual bandit only after collecting enough reviewed data. Do not infer causal effects from production correlations alone: rerun paired interventions in controlled fixture snapshots, retain confounders, and report where the simulator may not transfer.

## Baselines and ablations

| Condition | Change relative to baseline | What it tests |
|---|---|---|
| A | Frozen model, prompt, tools, fixed retrieval | Reproducible starting point |
| B | Effective-date/scoped retrieval only | Retrieval failure vs. context-use failure |
| C | Additional verification only | Whether extra inference earns latency/cost |
| D | Unknown-outcome reconciliation only | Tool reliability independent of language fluency |
| E | Reviewed operational memory only | Benefit and harm of prior experience |
| F | Bounded intervention selection | Choosing an intervention within budget |
| G | SFT adapter | Learning action structure from curated trajectories |
| H | DPO after SFT | Learning preferences without losing critical behavior |

Do not combine all changes before measuring their individual contributions. GRPO or DAPO is a later optional study when verifiable environment rewards are stable. Compare process supervision to outcome supervision separately; distinguish genuine transfer from memorized fixture structure.

## Environments and verifiable outcomes

Invoice environment: fake vendor, PO, receipt, policy and ERP state; duplicate invoices, partial delivery, tax/currency differences, outdated policies, tool timeouts, injected instructions, and missing evidence. Ground truth checks correct payable draft, discrepancy amount, correct reviewer, approval-before-write, no duplicate external action, and complete audit lineage.

Onboarding environment: fictional employees, manager relations, equipment inventory, start-date changes and delayed responses. Success means an internally consistent checklist and approved provisioning requests, not unapproved employment decisions.

Access environment: fictional roles, resources, expirations and manager tickets. Success means a justified least-privilege recommendation; unauthorized grants or cross-tenant access are critical failures.

Simulated users have configurable response delay, patience, clarification tolerance, and abandonment. Include honest stop/escalate as valid outcomes when required evidence is unavailable. Penalizing all stops would incentivize fabricated completion.

Reward safeguards: inspect final state, not prose; withhold protected records from tools; prevent repeated no-op rewards; verify amounts and identities; bind approval to the exact action; count silent failure and exhaustion; test exploitable shortcuts before training. Preserve examples of reward hacking in the report.

## Dataset and splits

Begin with a pilot of 30 distinct tasks across failure types and 5 repeats per condition. Estimate paired outcome variation, cost, and feasibility before fixing the final experiment size.

An illustrative scale target is 1,200 task families: 480 training, 120 development, 600 held-out (200 per workflow family). The target may change after the pilot. Group by tenant template, vendor/document family, request lineage and near-duplicate cluster **before** splitting. Synthetic paraphrases of one seed remain in its split. No held-out data enters prompt tuning, memory, retrieval tuning, preference curation, or training. Add later temporal/source-layout holdouts to probe transfer.

Freeze manifests with task IDs and content hashes. Record data permission and provenance. Review SFT targets for valid tool calls and evidence; review both sides of DPO pairs. A preferred fluent answer that performs an unauthorized action is not a positive example. Keep model-generated augmentations labeled and compare an augmentation-free baseline.

## Measurements

- Primary: complete-task success under the same fixed budget and stopping criteria.
- Critical constraints: tenant isolation, approval enforcement, no unauthorized writes, and no duplicated consequential effects.
- Secondary: retrieval recall and source freshness, appropriate clarification, evidence use, correct tool selection, schema validity, recovery correctness, and escalation rate.
- Operational: p50/p95 active latency, approval wait separately, tokens, tool retries, total cost per attempt and per success, and recovery duration.
- Reliability: report pass@1 and all-repeats-success alongside pass@k. Do not present pass@k as first-attempt production reliability.

Count every selected task, including crashes, timeouts, exhausted budgets, and missing results. Record whether a model was actually called. Report component and complete-workflow scores separately.

## Statistical judgment

Use paired tasks across candidates and identical environment snapshots, with multiple stochastic repetitions. Bootstrap by task family (cluster repeated runs), not by treating every step as an independent sample. Report paired uplift intervals and per-scenario results. Size the main study from pilot variance and a minimum practically useful effect. An illustrative design target is at least +5 percentage points task success without critical-policy regressions, but this is not a promised gain.

Set the analysis and stopping rules before viewing the held-out results. Correct for multiple candidates or use a separate final confirmation set. An interval crossing zero is inconclusive, not an improvement. A null result that rules out useful improvement should retire that intervention.

For zero observed critical failures, report sample size and uncertainty; zero failures does not prove zero risk. Use deterministic security assertions and adversarial tasks independently of an aggregate success score.

## Judges

Prefer code-based environment assertions for amounts, record existence, scopes and approval order. Use human review for ambiguous judgments. Calibrate any model judge against independently labeled examples, blind labels to candidate identity, randomize order, check position bias and verbosity bias, report disagreement/confusion and inter-rater agreement, and adjudicate critical disagreement. Do not use the candidate as its only judge.

## Promotion and rollback

Real evaluation evidence must include baseline/candidate/dataset hashes, complete result records, a valid held-out split, confidence intervals, costs, and required policy tests. The demo `promotionGate` is only a small UI/domain example; production authorization needs a complete validated report, authenticated approvals, and server-side checks.

Roll out to an isolated fixture tenant, then read-only shadow mode, then a small explicitly approved canary. Require enough observations and a timeout; inconclusive checks block promotion. Revert new-run routing if error rates, task success, or latency breach the predeclared limits. Never describe model rollback as reversal of irreversible business effects.

## Portfolio evidence

Publish a reproducible environment, synthetic benchmark definition, exact experiment configs, scripts, versioned results, representative failure traces, a dataset card, a model card if trained, an engineering handoff/runbook, and a short native-desktop demo. Document both positive and negative findings, simulator limitations, actual compute, and your specific contribution.
