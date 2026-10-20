# Veya work and evidence

Veya carries out delegated business work and records the evidence needed to review its actions and improve future behavior.

## Language

**Task:** The outcome a user asks Veya to achieve, with its supplied context and permitted scope.
_Avoid_: Prompt, job, run when referring to the user's persistent request.

**Run:** One attempt to carry out a task under a specific configuration and authority.
_Avoid_: Task when referring to an individual attempt.

**Step:** A recorded reasoning, observation or action within a run.
_Avoid_: Task when referring to one action.

**Proposal:** An exact proposed external change presented for authorization before it takes effect.
_Avoid_: Approval, completed action.

**Approval:** A reviewer's limited authorization for one specific proposal.
_Avoid_: General permission to act independently.

**Operation intent:** The business effect that should occur once even when execution is retried.
_Avoid_: Attempt identifier.

**Unknown outcome:** An issued action whose external effect has not yet been established.
_Avoid_: Failed, cancelled or safely retryable without further evidence.

**Artifact:** An identifiable input or output whose content and provenance can be inspected.
_Avoid_: Unattributed attachment.

**Memory:** A reviewed lesson or preference retained for future work within an explicit scope.
_Avoid_: Unrestricted conversation history.

**Environment:** A reproducible business situation in which an agent can act and its resulting state can be checked.
_Avoid_: Benchmark score, production tenant when using a fixture.

**Intervention:** A deliberate change intended to improve a particular failure behavior.
_Avoid_: Proven improvement before evaluation.

**Story:** One reviewable implementation change with observable acceptance criteria and code evidence.
_Avoid_: Planning document, research intention without an executable change.

**Deliverable:** A coherent capability accepted through its stories and an integration gate.
_Avoid_: A collection of completed checkboxes without working behavior.

**Release checkpoint:** A dependency-complete subset of the roadmap with a demonstrable user or research outcome.
_Avoid_: A promise to finish every roadmap item.
