"""Explicit synthetic evidence for isolated tests, never a model qualification report."""

from veya.research.models import (
    EvaluationReport,
    ExpectedRun,
    Interval,
    Outcome,
    TraceEvent,
    Trajectory,
)


def trace(key='fixture_trace', **changes):
    values = dict(
        id=key,
        case_id='fixture_case',
        family='fixture_family',
        lineage='fixture_lineage',
        conditions_hash='a' * 64,
        source='synthetic',
        split='train',
        source_ids=('fixture_source',),
        events=(
            TraceEvent(
                sequence=1,
                run_id='fixture_run',
                attempt=1,
                model_id='fixture_adapter',
                kind='start',
                content='Read the fixture order.',
            ),
            TraceEvent(
                sequence=2,
                run_id='fixture_run',
                attempt=1,
                model_id='fixture_adapter',
                kind='finish',
                content='The fixture amount is 12 USD.',
            ),
        ),
    )
    values.update(changes)
    return Trajectory(**values)


def report():
    from packages.evals.statistics import paired

    jobs = []
    rows = []
    for family in ('quantity', 'currency', 'approval'):
        for candidate in ('baseline', 'candidate'):
            key = family + '_' + candidate
            job = ExpectedRun(
                id=key,
                case_id='fixture_' + family,
                family=family,
                candidate=candidate,
                repetition=0,
                seed=1,
            )
            jobs.append(job)
            rows.append(
                Outcome(
                    **job.model_dump(),
                    source='synthetic',
                    status='failed' if candidate == 'baseline' else 'succeeded',
                    duration_ms=120,
                    tokens=10,
                    cost_microunits=0,
                    violations=0,
                    evidence_ids=(key + '_audit',),
                )
            )
    return EvaluationReport(
        id='fixture_comparison',
        title='Invoice review - synthetic comparison',
        spec_hash='a' * 64,
        expected_ids=tuple(j.id for j in jobs),
        expected_runs=tuple(jobs),
        outcomes=tuple(rows),
        baseline='baseline',
        candidate='candidate',
        interval=Interval(**paired(tuple(rows), 'baseline', 'candidate')),
    )
