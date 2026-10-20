"""Initialize the reviewed story seed once; ongoing state belongs in backlog.json."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / 'planning/backlog.json'


def main():
    if TARGET.exists():
        raise SystemExit('backlog.json already exists. Use project.py; do not reset delivery history.')
    epics = json.loads((ROOT / 'planning/epics.json').read_text(encoding='utf-8'))
    epic_map = {e['id']: e for e in epics}
    stories = []
    current = None
    # Optional experiments and infrastructure are explicitly outside the initial product commitment.
    stretch = {169,175,176,177,179,206,207,208,209,210,236,240,234,235,237,238,239}
    stretch.update(range(231,241))
    for line in (ROOT / 'planning/story-seed.txt').read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            current = line[3:]
        elif line and not line.startswith('#'):
            parts = line.split(' | ')
            if len(parts) != 7 or current not in epic_map:
                raise ValueError(f'Invalid story row: {line}')
            title, change, accepted, negative, paths, deps, hours = parts
            number = len(stories) + 1
            base = int(hours)
            epic = epic_map[current]
            stories.append({
                'id': f'VEY-{number:03}', 'title': title, 'epic_id': current,
                'deliverable_id': 'D' + current[1:], 'goal_id': epic['goal'],
                'milestone_id': epic['milestone'], 'actor': epic['persona'],
                'user_value': epic['outcome'], 'code_change': change,
                'acceptance_criteria': [accepted, negative],
                'code_paths': paths.split(';'),
                'verification': f'Exercise the changed entry point and assert: {accepted}. Negative case: {negative}. Retain the test command, result and evidence artifact.',
                'depends_on': [] if deps == '-' else [f'VEY-{int(n):03}' for n in deps.split(',')],
                'estimate_hours': {'low': max(1,math.floor(base*.75)), 'base':base, 'high':math.ceil(base*1.5)},
                'scope': 'Stretch' if number in stretch else ('Research' if current in {'E16','E17','E18'} else 'Core'),
                'priority': 'P2' if number in stretch else 'P1',
                'status':'backlog', 'owner':'Unassigned', 'actual_hours':None,
                'commit':None, 'evidence':[], 'acceptance_note':None, 'blocked_reason':None,
                'updated_at':'2026-10-20',
            })
    index = {s['id']:s for s in stories}
    def closure(numbers):
        found = set()
        def visit(sid):
            if sid in found:
                return
            found.add(sid)
            for dependency in index[sid]['depends_on']:
                visit(dependency)
        for number in numbers:
            visit(f'VEY-{number:03}')
        return sorted(found)
    releases = [
        {'id':'R0','name':'Native recovery checkpoint','scope':'Repair the existing startup failure and apply the working identity. This is not a functioning AI employee.','story_ids':closure([2,11]),'acceptance':'A packaged native window stays open and displays the Veya shell with startup diagnostics retained.'},
        {'id':'R1','name':'First real delegated task','scope':'One read-only document task through the desktop, a real local model and typed tools.','story_ids':closure([22,23,26,47,52,67,72,78]),'acceptance':'User submits an instruction and document; the model uses permitted tools and returns a cited result. Failure and cancellation remain explicit.'},
        {'id':'R2','name':'Invoice MVP','scope':'Invoice discrepancy resolution, approval and one verified fixture-ERP draft write. No real payments.','story_ids':closure([90,29,30,214]),'acceptance':'The native workflow completes the invoice acceptance suite with real inference, evidence, review, idempotency and verified final fixture state.'},
        {'id':'R3','name':'Evaluation and learning beta','scope':'Repeatable environments, meaningful baseline comparison, one SFT experiment and intervention evaluation.','story_ids':closure([90,119,129,149,150,159,163,166,168,178]),'acceptance':'A reproducible report measures held-out task outcomes, uncertainty, violations, latency and cost. Negative results are valid research outcomes.'},
        {'id':'R4','name':'Operational desktop release','scope':'Core and research roadmap with team services and distribution; optional stretch remains separately selectable.','story_ids':[s['id'] for s in stories if s['scope']!='Stretch'],'acceptance':'Required core and research deliverables pass their gates, native install/upgrade is verified, and configured GitHub pipelines have real successful runs.'},
        {'id':'R5','name':'Full optional research roadmap','scope':'All 240 stories, including experiments and additional workflows. This is not the first-release commitment.','story_ids':[s['id'] for s in stories],'acceptance':'All selected extensions have their own evidence and no unsupported claims of novelty or production scale.'}
    ]
    # Pull prerequisites into the earliest consumer milestone; milestone order is not an artificial blocker.
    for sid in ['VEY-021','VEY-031','VEY-211']:
        index[sid]['milestone_id']='M0'
    index['VEY-214']['milestone_id']='M2'
    changed=True
    while changed:
        changed=False
        for story in stories:
            for dep in story['depends_on']:
                if index[dep]['milestone_id'] > story['milestone_id']:
                    index[dep]['milestone_id']=story['milestone_id']
                    changed=True
    for sid in set(releases[2]['story_ids']):
        index[sid]['priority']='P0'
    for story in stories:
        story['release_ids']=[r['id'] for r in releases if story['id'] in r['story_ids']]
    for epic in epics:
        epic['deliverable_id']='D'+epic['id'][1:]
        epic['acceptance_status']='pending'
        epic['acceptance_evidence']=[]
        epic['accepted_at']=None
    data={
        'schema_version':1,
        'project':{'name':'Veya','working_name':True,'slug':'veya','story_prefix':'VEY','created_at':'2026-10-20','baseline_commit':'2e29edd','requested_root':r'C:\Users\Swarneil Pradhan\Project\Veya','target_access':'denied in current session','planning_version':'1.0'},
        'capacity':{'hours_per_week_scenarios':[12,15,18], 'integration_contingency':0.25,'notes':'Hours are uncalibrated engineering estimates. The range is not a statistical confidence interval. No completion date is promised.'},
        'goals':[
            {'id':'G1','goal':'Delegate useful business work from a native desktop','measure':'A user submits an instruction and obtains a verified result without manually driving each step','initial_gate':'R2 invoice acceptance suite; synthetic business data, real model execution'},
            {'id':'G2','goal':'Make actions durable and recoverable','measure':'Crash, retry, cancellation and unknown-outcome scenarios preserve correct business state','initial_gate':'Zero duplicate business effects in the declared fault suite'},
            {'id':'G3','goal':'Keep agent actions inside explicit authority','measure':'Policy checks run immediately before effects and all adversarial denial scenarios leave no forbidden effects','initial_gate':'No unauthorized effects in the declared suite; this is not a universal security guarantee'},
            {'id':'G4','goal':'Measure behavior honestly','measure':'Held-out task-family splits, repeated runs, calibrated judges and paired uncertainty','initial_gate':'Reproducible baseline and candidate reports with complete denominators'},
            {'id':'G5','goal':'Complete a defensible learning experiment','measure':'One SFT experiment and a cheaper-intervention comparison with data lineage, latency and cost','initial_gate':'Publishable local experiment artifacts even when the result is negative'},
            {'id':'G6','goal':'Deliver maintainable and operable software','measure':'Clean environment builds, real CI runs, telemetry, native install/upgrade and rollback evidence','initial_gate':'R4 evidence gates; signing only if credentials are configured'},
            {'id':'G7','goal':'Make the engine extensible','measure':'Additional task families and contributor-owned adapters use stable contracts','initial_gate':'Optional R5 transfer and conformance evidence'}
        ],
        'milestones':[
            {'id':'M0','name':'Engineering foundation and native recovery','exit':'Stable packaged startup, validated contracts and reproducible checks'},
            {'id':'M1','name':'Real delegated work','exit':'A user instruction drives a bounded real-model read-only task'},
            {'id':'M2','name':'Invoice employee MVP','exit':'Evidence, review, one idempotent draft effect and verified finance output'},
            {'id':'M3','name':'Durable connected team execution','exit':'Remote workflow recovery and isolated sandbox integrations'},
            {'id':'M4','name':'Knowledge, environments and evaluation','exit':'Scoped context and repeatable held-out behavior measurement'},
            {'id':'M5','name':'Data engine and learning experiments','exit':'Approved data and a reproducible baseline-versus-candidate report'},
            {'id':'M6','name':'Operational release and distribution','exit':'Actual CI evidence, security tests, native install/upgrade and recovery'},
            {'id':'M7','name':'Optional extensions and transfer','exit':'Selected extensions pass shared contracts and transfer evaluation'}
        ],
        'epics':epics,'releases':releases,'stories':stories,'history':[],
        'planning_deliverables':[
            {'id':'P01','name':'Comprehensive scope and goals','status':'delivered','path':'planning/SCOPE.md'},
            {'id':'P02','name':'240 code-change stories','status':'delivered','path':'planning/BACKLOG.md'},
            {'id':'P03','name':'Milestones and deliverable register','status':'delivered','path':'planning/DELIVERABLES.md'},
            {'id':'P04','name':'Persistent status tracker and update tool','status':'delivered','path':'scripts/project.py'},
            {'id':'P05','name':'Risks, decisions and release strategy','status':'delivered','path':'planning/RISKS.md'},
            {'id':'P06','name':'GitHub-ready issue payloads','status':'delivered','path':'planning/github-issues.json'}
        ]
    }
    TARGET.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Initialized {len(stories)} stories across {len(epics)} epics.')


if __name__=='__main__':
    main()
