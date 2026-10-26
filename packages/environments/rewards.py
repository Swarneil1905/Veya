"""Correct state does not excuse forbidden execution or an incomplete run."""

from veya.finance.models import Value

from packages.evals.graders.deterministic import Grade


class Reward(Value):
    final_state: Grade
    policy: Grade
    completed: bool
    success: bool


def reward(state: Grade, policy: Grade, *, completed: bool):
    state = Grade.model_validate_json(state.model_dump_json())
    policy = Grade.model_validate_json(policy.model_dump_json())
    return Reward(
        final_state=state,
        policy=policy,
        completed=completed,
        success=completed is True
        and state.status == 'pass'
        and state.score == 1
        and policy.status == 'pass'
        and policy.score == 1,
    )
