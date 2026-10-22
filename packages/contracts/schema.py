"""Export the versioned domain schema; HTTP client generation is VEY-007."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/runtime'))
from pydantic import TypeAdapter
from veya.domain.models import Artifact, Error, Run, Step, Task

schema = {'version': 1, 'models': {
    model.__name__: TypeAdapter(model).json_schema()
    for model in (Task, Run, Step, Artifact, Error)
}}
(Path(__file__).parent / 'schema.json').write_text(
    json.dumps(schema, indent=2, sort_keys=True) + '\n', encoding='utf-8')
