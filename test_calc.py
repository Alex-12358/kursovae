import sys
import json
sys.path.insert(0, '.')
from calc.engine import run_calculations

with open('data/input/task.json', encoding='utf-8') as f:
    task = json.load(f)
result = run_calculations(task)
print(json.dumps(result['calc_trace'], ensure_ascii=False, indent=2))
