"""Explicitly inconclusive evidence cannot approve a model. This never deploys anything."""

import math


def assess(
    *,
    baseline,
    candidate,
    interval,
    leakage_passed,
    judge_calibration,
    source,
    minimum_gain=0.0,
    max_cost_microunits=1000000,
    max_p95_ms=120000,
    minimum_families=2,
):
    reasons = []
    try:
        if (
            not isinstance(minimum_gain, (int, float))
            or not math.isfinite(minimum_gain)
            or minimum_gain < 0
            or minimum_families < 2
        ):
            raise ValueError()
        if source != 'model':
            reasons.append('synthetic_evidence')
        if leakage_passed is not True:
            reasons.append('leakage_or_missing_check')
        if (
            judge_calibration is not None
            and judge_calibration.get('promotion_eligible') is not True
        ):
            reasons.append('uncalibrated_judge')
        for limit in [max_cost_microunits, max_p95_ms, minimum_families]:
            if type(limit) is not int or limit < 0:
                raise ValueError()
        for metrics in [baseline, candidate]:
            for name in [
                'denominator',
                'successes',
                'known_cost_microunits',
                'missing_cost_count',
                'violations',
                'p95_ms',
            ]:
                if type(metrics[name]) is not int or metrics[name] < 0:
                    raise ValueError()
            if metrics['successes'] > metrics['denominator']:
                raise ValueError()
            if not isinstance(metrics['task_set_hash'], str) or len(metrics['task_set_hash']) != 64:
                raise ValueError()

            if metrics['complete'] is not True or metrics['denominator'] <= 0 or metrics['missing']:
                reasons.append('incomplete_runs')
            if metrics['missing_cost_count'] != 0:
                reasons.append('unknown_cost')
        if (
            candidate['denominator'] != baseline['denominator']
            or candidate['currency'] != baseline['currency']
            or candidate['task_set_hash'] != baseline['task_set_hash']
        ):
            reasons.append('unmatched_comparison')
        if candidate['violations'] != 0:
            reasons.append('policy_violation')
        if (
            candidate['known_cost_microunits'] > max_cost_microunits
            or candidate['p95_ms'] > max_p95_ms
        ):
            reasons.append('resource_budget')
        if (
            any(
                type(interval[k]) not in (int, float)
                or not math.isfinite(interval[k])
                or not -1 <= interval[k] <= 1
                for k in ['low', 'high', 'delta']
            )
            or interval['low'] > interval['high']
        ):
            raise ValueError()
        if (
            interval['status'] != 'estimated'
            or interval['independent_units'] < minimum_families
            or not math.isfinite(interval['low'])
            or interval['low'] <= minimum_gain
        ):
            reasons.append('inconclusive_benefit')
    except (KeyError, TypeError, ValueError):
        reasons.append('missing_or_invalid_metrics')
    return {'status': 'pass' if not reasons else 'blocked', 'reasons': sorted(set(reasons))}


def qualify(report, *, leakage_passed, judge_calibration=None, **policy):
    """Derive all metrics and intervals from one immutable report, not caller-supplied scores."""
    from veya.research.models import EvaluationReport

    from packages.evals.metrics import compare
    from packages.evals.statistics import paired

    report = EvaluationReport.model_validate_json(report.model_dump_json())
    expected = {
        name: tuple(j.id for j in report.expected_runs if j.candidate == name)
        for name in (report.baseline, report.candidate)
    }
    try:
        metrics = compare(expected, report.outcomes)
    except ValueError:
        return {'status': 'blocked', 'reasons': ['unmatched_comparison']}
    source = (
        'model'
        if report.outcomes and all(r.source == 'model' for r in report.outcomes)
        else 'synthetic'
    )
    interval = paired(
        report.outcomes,
        report.baseline,
        report.candidate,
        seed=report.interval.seed,
        draws=report.interval.draws,
    )
    return assess(
        baseline=metrics[report.baseline],
        candidate=metrics[report.candidate],
        interval=interval,
        leakage_passed=leakage_passed,
        judge_calibration=judge_calibration,
        source=source,
        **policy,
    )
