"""Synthetic result fixture for the owned browser-test workspace only."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/runtime'))
from veya.storage.sqlite import Database
from veya.storage.submission import submit
from veya.storage.run_state import transition_run
from veya.ingestion.jobs import Documents
from veya.artifacts.store import ArtifactStore

root=Path(sys.argv[1]).resolve()
if not root.is_relative_to(ROOT/'artifacts'/'document-batch') or not root.name.startswith('workspace-'):
    raise ValueError('Synthetic workspace required')
db=Database(root);docs=Documents(db,'desktop')
item=docs.intake('fixture_source','Fixture order.csv',b'amount,currency\n12.30,USD\n')
ready=docs.process(item['id'])
task,run,_=submit(db,'desktop','fixture_result','Fixture completed order','Synthetic result inspection. No model execution.',document_ids=[item['id']])
run=transition_run(db,'desktop',run.id,'running',run.revision)
run=transition_run(db,'desktop',run.id,'succeeded',run.revision)
ArtifactStore(db).put('desktop',run.id,json.dumps({'claims':[{'text':'The fixture amount is 12.30 USD.','citations':[ready['blocks'][0]['citation'],'doc_unavailable:0']}], 'exceptions':['Supplier confirmation is outstanding.']}).encode(),'Fixture result.json','application/json')
