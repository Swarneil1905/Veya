"""Maintain Veya's local delivery ledger. No network access or issue publication."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fnmatch
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {'backlog', 'in_progress', 'blocked', 'in_review', 'done'}
ALLOWED = {
    'backlog': {'in_progress', 'blocked'},
    'in_progress': {'in_review', 'blocked', 'backlog'},
    'blocked': {'backlog', 'in_progress'},
    'in_review': {'done', 'in_progress', 'blocked'},
    'done': {'in_progress'},
}


def load(root: Path = ROOT) -> dict:
    return json.loads((root / 'planning/backlog.json').read_text(encoding='utf-8'))


def validate(data: dict) -> None:
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported backlog schema')
    stories = data['stories']
    ids = [s['id'] for s in stories]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate story ID')
    if len(stories) < 201:
        raise ValueError('The comprehensive roadmap must contain more than 200 stories')
    index = {s['id']: s for s in stories}
    epics = {e['id'] for e in data['epics']}
    goals = {g['id'] for g in data['goals']}
    milestones = {m['id'] for m in data['milestones']}
    names = set()
    for story in stories:
        if not re.fullmatch(r'VEY-\d{3,}', story['id']):
            raise ValueError('Invalid story identifier')
        if story['title'].casefold() in names:
            raise ValueError(f'Duplicate title: {story["id"]}')
        names.add(story['title'].casefold())
        if story['epic_id'] not in epics or story['goal_id'] not in goals or story['milestone_id'] not in milestones:
            raise ValueError(f'Unknown planning reference: {story["id"]}')
        if story['status'] not in STATUSES:
            raise ValueError(f'Invalid status: {story["id"]}')
        if not story['code_change'] or len(story['acceptance_criteria']) < 2 or not story['verification']:
            raise ValueError(f'Missing implementation/acceptance details: {story["id"]}')
        if not story['code_paths'] or all(p.endswith('.md') for p in story['code_paths']):
            raise ValueError(f'Documentation-only story: {story["id"]}')
        for path in story['code_paths']:
            if Path(path).is_absolute() or '..' in Path(path).parts or ':' in path:
                raise ValueError(f'Unsafe target path: {story["id"]}')
        bounds = story['estimate_hours']
        if not 0 < bounds['low'] <= bounds['base'] <= bounds['high']:
            raise ValueError(f'Invalid effort range: {story["id"]}')
        if story['actual_hours'] is not None and (not math.isfinite(story['actual_hours']) or story['actual_hours'] < 0):
            raise ValueError('Actual hours must be finite and nonnegative')
        for dependency in story['depends_on']:
            if dependency not in index:
                raise ValueError(f'Unknown dependency {dependency} on {story["id"]}')
            if index[dependency]['milestone_id'] > story['milestone_id']:
                raise ValueError(f'Prerequisite scheduled after consumer: {dependency}')
        if story['status'] == 'done':
            if not story['commit'] or not story['evidence'] or not story['acceptance_note']:
                raise ValueError(f'Done story lacks completion evidence: {story["id"]}')
            if any(index[d]['status'] != 'done' for d in story['depends_on']):
                raise ValueError(f'Done story has incomplete dependency: {story["id"]}')
        if story['status'] == 'blocked' and not story['blocked_reason']:
            raise ValueError(f'Blocked story lacks reason: {story["id"]}')
    visited, active = set(), set()
    def visit(sid):
        if sid in active:
            raise ValueError(f'Dependency cycle at {sid}')
        if sid in visited:
            return
        active.add(sid)
        for dep in index[sid]['depends_on']:
            visit(dep)
        active.remove(sid)
        visited.add(sid)
    for sid in ids:
        visit(sid)
    for epic in data['epics']:
        if epic['acceptance_status'] == 'accepted':
            rows = [s for s in stories if s['epic_id'] == epic['id']]
            if not rows or any(s['status'] != 'done' for s in rows) or not epic['acceptance_evidence']:
                raise ValueError(f'Accepted deliverable has incomplete work or evidence: {epic["id"]}')
    for release in data['releases']:
        scope = set(release['story_ids'])
        if not scope.issubset(index):
            raise ValueError('Release references an unknown story')
        for sid in scope:
            if not set(index[sid]['depends_on']).issubset(scope):
                raise ValueError(f'Release {release["id"]} omits prerequisites for {sid}')


def ready_stories(data: dict) -> list[dict]:
    index = {s['id']: s for s in data['stories']}
    candidates = [s for s in data['stories'] if s['status'] == 'backlog' and all(index[d]['status'] == 'done' for d in s['depends_on'])]
    return sorted(candidates, key=lambda s: (s['priority'], s['milestone_id'], s['id']))


def git_output(root: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, check=False, timeout=20)
    if result.returncode:
        raise ValueError('Git evidence verification failed: ' + result.stderr.strip())
    return result.stdout.strip()


def verify_completion(root: Path, data: dict, story: dict, commit: str, evidence: list[str], note: str) -> str:
    if not commit or not re.fullmatch(r'[0-9a-fA-F]{7,40}', commit):
        raise ValueError('A real hexadecimal commit ID is required')
    resolved = git_output(root, 'rev-parse', '--verify', commit + '^{commit}')
    baseline = git_output(root, 'rev-parse', '--verify', data['project']['baseline_commit'] + '^{commit}')
    if resolved == baseline:
        raise ValueError('The prototype baseline cannot complete a planned story')
    git_output(root, 'merge-base', '--is-ancestor', baseline, resolved)
    changed = git_output(root, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', resolved).splitlines()
    if not any(fnmatch.fnmatchcase(path, target) or path.startswith(target.rstrip('/') + '/') for path in changed for target in story['code_paths']):
        raise ValueError('Commit does not change a declared code path for this story')
    if not evidence or not note or len(note.strip()) < 12:
        raise ValueError('Evidence files and a meaningful acceptance note are required')
    for relative in evidence:
        path = (root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Evidence must be a nonempty repository-relative file: ' + relative)
    return resolved


def transition(root: Path, data: dict, sid: str, target: str, *, owner=None, reason=None, commit=None, evidence=None, note=None, actual_hours=None) -> None:
    validate(data)
    index = {s['id']: s for s in data['stories']}
    if sid not in index:
        raise ValueError('Unknown story: ' + sid)
    story = index[sid]
    before = story['status']
    if target not in ALLOWED[before]:
        raise ValueError(f'Invalid transition: {before} -> {target}')
    if target in {'in_progress', 'in_review', 'done'} and any(index[d]['status'] != 'done' for d in story['depends_on']):
        raise ValueError('Complete the dependencies before starting or completing this story')
    if target == 'blocked' and not reason:
        raise ValueError('A blocked reason is required')
    if before == 'done':
        if not reason:
            raise ValueError('Reopening requires a reason')
        dependents = [s['id'] for s in data['stories'] if sid in s['depends_on'] and s['status'] != 'backlog']
        if dependents:
            raise ValueError('Reopen downstream stories first: ' + ', '.join(dependents))
    if actual_hours is not None and (not math.isfinite(actual_hours) or actual_hours < 0):
        raise ValueError('Actual hours must be a finite nonnegative number')
    if target == 'done':
        resolved = verify_completion(root, data, story, commit, evidence or [], note)
        story.update(commit=resolved, evidence=evidence, acceptance_note=note, actual_hours=actual_hours)
    if before == 'done':
        story.update(commit=None, evidence=[], acceptance_note=None, actual_hours=None)
        for epic in data['epics']:
            if epic['id'] == story['epic_id']:
                epic.update(acceptance_status='pending', acceptance_evidence=[], accepted_at=None)
    when = datetime.now(timezone.utc).isoformat(timespec='seconds')
    story.update(status=target, updated_at=when, blocked_reason=reason if target == 'blocked' else None)
    if owner:
        story['owner'] = owner
    data['history'].append({'at':when,'story_id':sid,'from':before,'to':target,'reason':reason,'commit':story['commit'],'evidence':story['evidence'],'acceptance_note':note})
    validate(data)


@contextmanager
def locked(root: Path):
    path = root / 'planning/.tracker.lock'
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError('Another tracker update holds the lock; inspect it before retrying') from error
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def save(data: dict, root: Path = ROOT) -> None:
    validate(data)
    target = root / 'planning/backlog.json'
    fd, temp = tempfile.mkstemp(prefix='backlog-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def summary(data: dict) -> dict:
    return {'project':data['project']['name'], 'stories':len(data['stories']), 'epics':len(data['epics']),
            'status_counts':{state:sum(s['status']==state for s in data['stories']) for state in sorted(STATUSES)},
            'ready':len(ready_stories(data)), 'effort_hours':{key:sum(s['estimate_hours'][key] for s in data['stories']) for key in ['low','base','high']}}


def story_body(story: dict) -> str:
    effort = story['estimate_hours']
    return '\n'.join([
        f'## {story["id"]}: {story["title"]}', '',
        f'**Actor:** {story["actor"]}. **User value:** {story["user_value"]}.', '',
        f'**Code change:** {story["code_change"]}.', '',
        '**Acceptance criteria:**', '', *[f'- [ ] {criterion}.' for criterion in story['acceptance_criteria']], '',
        f'**Target code:** {", ".join("`"+p+"`" for p in story["code_paths"])}.', '',
        f'**Verification:** {story["verification"]}', '',
        f'**Dependencies:** {", ".join(story["depends_on"]) or "None"}.', '',
        f'**Tracking:** {story["status"]}; {story["priority"]}; {story["scope"]}; {story["milestone_id"]}; {story["deliverable_id"]}; owner: {story["owner"]}.', '',
        f'**Effort:** {effort["base"]} base hours; planning range {effort["low"]}-{effort["high"]} hours, before shared integration allowance.', '',
        f'**Completion evidence:** {story["commit"] or "No implementation commit recorded"}; {", ".join(story["evidence"]) or "no test evidence recorded"}.', ''
    ])


def render(data: dict, root: Path = ROOT) -> None:
    validate(data)
    index = {s['id']:s for s in data['stories']}
    stats = summary(data)
    planning = root / 'planning'
    backlog = ['# Veya code-change backlog', '', 'Generated from `backlog.json`. Edit canonical state with `python scripts/project.py`; do not use checkboxes here as the status source.', '',
               'Every story requires a code/configuration/migration/test change. Documentation-only planning work is listed separately in STATUS.md. Target paths describe the intended architecture and may not exist yet.', '',
               '| Epic | Area | Stories |', '| --- | --- | --- |']
    backlog += [f'| {e["id"]} | {e["name"]} | {sum(s["epic_id"]==e["id"] for s in data["stories"])} |' for e in data['epics']]
    for epic in data['epics']:
        backlog += ['', f'# {epic["id"]}: {epic["name"]}', '', f'**Deliverable:** {epic["deliverable"]}.', '', f'**Acceptance gate:** {epic["acceptance"]}', '']
        backlog += [story_body(s) for s in data['stories'] if s['epic_id']==epic['id']]
    (planning/'BACKLOG.md').write_text('\n'.join(backlog)+'\n',encoding='utf-8')
    status = ['# Veya delivery status', '', 'Canonical source: `planning/backlog.json`. This report is regenerated after every tracker update. Story counts reflect accepted implementation evidence, not planning effort.', '',
              f'**Build progress: {stats["status_counts"]["done"]}/{stats["stories"]} stories done.** Ready to start: {stats["ready"]}.', '',
              '| Status | Stories |', '| --- | ---: |']
    status += [f'| {state} | {count} |' for state,count in stats['status_counts'].items()]
    status += ['', '## Release scope and effort', '', 'Release scopes are cumulative through dependencies where applicable; do not add their totals together. Hours are uncalibrated estimates, not measured productivity or promised dates. Each scope includes its full prerequisite closure.', '',
               '| Release | Stories | Done | Base hours | Range hours | Base with 25% integration allowance | Weeks at 15 h/week |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for release in data['releases']:
        rows=[index[sid] for sid in release['story_ids']]
        estimates={k:sum(s['estimate_hours'][k] for s in rows) for k in ['low','base','high']}
        adjusted=math.ceil(estimates['base']*1.25)
        status.append(f'| {release["id"]}: {release["name"]} | {len(rows)} | {sum(s["status"]=="done" for s in rows)} | {estimates["base"]} | {estimates["low"]}-{estimates["high"]} | {adjusted} | {math.ceil(adjusted/15)} |')
    status += ['', '## Ready queue', '', '| Story | Code change | Base hours |', '| --- | --- | ---: |']
    status += [f'| {s["id"]} | {s["title"]} | {s["estimate_hours"]["base"]} |' for s in ready_stories(data)[:12]]
    status += ['', '## Planning deliverables', '', '| ID | Deliverable | Status | File |', '| --- | --- | --- | --- |']
    status += [f'| {p["id"]} | {p["name"]} | {p["status"]} | `{p["path"]}` |' for p in data['planning_deliverables']]
    status += ['', '## Active blockers', '', 'See RISKS.md. Repository access and history reconciliation are resolved. Native startup and rendered UI remain unverified; desktop-to-runtime wiring, inference, live connectors and GitHub CI remain open.', '', '## Recent tracker events', '']
    status += [f'- {h["at"]}: {h.get("story_id",h.get("deliverable_id"))} {h.get("from","")} -> {h.get("to","")}' for h in data['history'][-10:]] or ['No implementation transitions recorded.']
    (planning/'STATUS.md').write_text('\n'.join(status)+'\n',encoding='utf-8')
    lines=['# Veya deliverables and milestones','','A deliverable is accepted only after its stories are done and its integration gate has evidence. Optional stories may remain outside an earlier release scope; accepting the full deliverable requires all of its listed stories.','','| ID | Deliverable | Stories done | Status | Acceptance gate |','| --- | --- | ---: | --- | --- |']
    for epic in data['epics']:
        rows=[s for s in data['stories'] if s['epic_id']==epic['id']]
        done=sum(s['status']=='done' for s in rows)
        state='accepted' if epic['acceptance_status']=='accepted' else ('awaiting acceptance' if done==len(rows) else ('in progress' if any(s['status']!='backlog' for s in rows) else 'not started'))
        lines.append(f'| {epic["deliverable_id"]} | {epic["deliverable"]} | {done}/{len(rows)} | {state} | {epic["acceptance"]} |')
    lines += ['', '## Milestones', '', 'Prerequisites are pulled into the earliest milestone that consumes them. A milestone groups work and defines an exit; it does not require unrelated work to finish before a ready story can start.', '', '| Milestone | Story count | Base hours | Exit evidence |','| --- | ---: | ---: | --- |']
    for milestone in data['milestones']:
        rows=[s for s in data['stories'] if s['milestone_id']==milestone['id']]
        lines.append(f'| {milestone["id"]}: {milestone["name"]} | {len(rows)} | {sum(s["estimate_hours"]["base"] for s in rows)} | {milestone["exit"]} |')
    lines += ['', '## Release acceptance', '']
    for release in data['releases']:
        lines += [f'### {release["id"]}: {release["name"]}', '', release['scope'], '', '**Exit:** '+release['acceptance'], '', '**Stories:** '+', '.join(release['story_ids']), '']
    (planning/'DELIVERABLES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    issues=[{'external_id':s['id'],'title':s['id']+': '+s['title'],'body':story_body(s),'labels':['type:story','epic:'+s['epic_id'],'priority:'+s['priority'],'scope:'+s['scope'].lower()],'milestone':s['milestone_id']} for s in data['stories']]
    (planning/'github-issues.json').write_text(json.dumps({'published':False,'note':'Prepared issue payloads only. No GitHub issues have been created. Dependency IDs are local references until issue-number mapping is established.','issues':issues},indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('validate'); sub.add_parser('status'); sub.add_parser('render')
    next_parser=sub.add_parser('next'); next_parser.add_argument('--limit',type=int,default=10)
    show=sub.add_parser('show'); show.add_argument('story')
    change=sub.add_parser('transition'); change.add_argument('story'); change.add_argument('status',choices=sorted(STATUSES))
    for flag in ['owner','reason','commit','note']:
        change.add_argument('--'+flag)
    change.add_argument('--evidence',action='append',default=[])
    change.add_argument('--actual-hours',type=float)
    accept=sub.add_parser('accept-deliverable'); accept.add_argument('deliverable'); accept.add_argument('--evidence',action='append',required=True)
    args=parser.parse_args()
    try:
        if args.command in {'transition','accept-deliverable','render'}:
            with locked(ROOT):
                data=load(); validate(data)
                if args.command=='transition':
                    transition(ROOT,data,args.story,args.status,owner=args.owner,reason=args.reason,commit=args.commit,evidence=args.evidence,note=args.note,actual_hours=args.actual_hours)
                    save(data)
                elif args.command=='accept-deliverable':
                    matches=[e for e in data['epics'] if e['deliverable_id']==args.deliverable]
                    if not matches:
                        raise ValueError('Unknown deliverable')
                    epic=matches[0]
                    if any(s['status']!='done' for s in data['stories'] if s['epic_id']==epic['id']):
                        raise ValueError('All deliverable stories must be done before integration acceptance')
                    for relative in args.evidence:
                        path=(ROOT/relative).resolve()
                        if Path(relative).is_absolute() or not path.is_relative_to(ROOT) or not path.is_file() or not path.stat().st_size:
                            raise ValueError('Provide nonempty repository-relative integration evidence')
                    when=datetime.now(timezone.utc).isoformat(timespec='seconds')
                    epic.update(acceptance_status='accepted',acceptance_evidence=args.evidence,accepted_at=when)
                    data['history'].append({'at':when,'deliverable_id':args.deliverable,'to':'accepted','evidence':args.evidence})
                    save(data)
                render(data)
                print(json.dumps(summary(data),indent=2))
        else:
            data=load(); validate(data)
            if args.command=='validate':
                print(f'PASS: {len(data["stories"])} unique code-change stories; dependency DAG and release closures valid.')
            elif args.command=='status':
                print(json.dumps(summary(data),indent=2))
            elif args.command=='next':
                for story in ready_stories(data)[:max(0,args.limit)]:
                    print(f'{story["id"]} [{story["priority"]}] {story["title"]}')
            else:
                matches=[s for s in data['stories'] if s['id']==args.story]
                if not matches:
                    raise ValueError('Unknown story')
                print(story_body(matches[0]))
    except (ValueError,KeyError,FileNotFoundError) as error:
        parser.exit(2, f'Error: {error}\n')


if __name__=='__main__':
    main()
