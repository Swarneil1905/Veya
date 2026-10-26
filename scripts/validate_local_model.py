"""Opt-in, synthetic-only local model smoke check. Never downloads or promotes a model."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/runtime'))
from veya.execution.agent_loop import Agent
from veya.ingestion.jobs import Documents
from veya.providers.models import ModelCapabilities, ModelConfig
from veya.providers.settings import Connections
from veya.storage.sqlite import Database
from veya.storage.submission import submit

async def validate(args):
    output = ROOT / 'artifacts' / 'provider-batch'
    output.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='live-validation-', dir=output))
    db = Database(root)
    config = ModelConfig(id='validation', provider_id='local', profile='local',
                         model_name=args.model, endpoint=args.endpoint,
                         capabilities=ModelCapabilities(tools=True, streaming=True,
                                                        context_tokens=args.context, max_output_tokens=1024))
    connections = Connections(db, 'fixture_validation')
    check = await connections.check(config, False)
    connections.activate([check['fingerprint']])
    documents = Documents(db, 'fixture_validation')
    doc = documents.intake('source', 'Synthetic.csv', b'code\nORCHID-482\n')
    documents.process(doc['id'])
    instruction = ('Read the source using the excerpt tool with citation ' + doc['id'] + ':0. '
                   'Report the code found there. Return only JSON with summary, citations and exceptions keys.')
    _, run, _ = submit(db, 'fixture_validation', 'once', 'Synthetic local model check',
                       instruction, document_ids=[doc['id']])
    agent = Agent(db, 'fixture_validation', connections)
    await agent.start(run.id, [config.fingerprint], False)
    await agent.running[run.id]
    with db.connection() as c:
        outcome = c.execute('SELECT outcome FROM agent_jobs').fetchone()[0]
        artifacts = c.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0]
    result = {'model': args.model, 'connection': check, 'run_state': db.get_run('fixture_validation', run.id).state,
              'outcome': outcome, 'artifact_count': artifacts, 'synthetic_only': True,
              'quality_qualification': 'One smoke check is not model qualification or production approval.'}
    (output / 'live-validation.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['run_state'] == 'succeeded' else 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434/v1')
    parser.add_argument('--context', type=int, default=4096)
    sys.exit(asyncio.run(validate(parser.parse_args())))
