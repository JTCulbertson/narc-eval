"""Run the NARC eval against models served from an OpenAI-compatible endpoint.

Usage examples:
  python run_eval.py text                         # text grids + narrative
  python run_eval.py text --condition grids_only  # text grids only
  python run_eval.py text --condition both grids_only narrative_only  # one run per condition
  python run_eval.py visual                       # rendered puzzle images (run render_puzzles.py first)
  python run_eval.py visual --limit 0 --models openai/qwen/qwen3.6-27b
  python run_eval.py visual --mapping colors patterns_default patterns_shuffle1  # one run per mapping
    (render pattern images first: python render_puzzles.py --mapping <names>; manage mappings with mappings.py)

Run with -h to see all options.
"""
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval

from mappings import COLORS, list_mappings

TASKS_FILE = Path(__file__).parent / "tasks.py"

# Tasks defined in tasks.py, with the models to run each one on by default
TASKS = {
    "text": {
        "task": f"{TASKS_FILE}@narc_eval",
        "models": [
            "openai/qwen/qwen3.8-27b",
            #"openai/Nemotron-3-Super-120b",
        ],
    },
    "visual": {
        "task": f"{TASKS_FILE}@narc_eval_visual",
        # Visual task needs vision-capable models
        "models": [
            "openai/qwen/qwen3.6-27b",
        ],
    },
}

parser = argparse.ArgumentParser(
    description="Run the NARC eval on models from an OpenAI-compatible endpoint.",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("task", choices=TASKS.keys(), help="which task to run")
parser.add_argument("--condition", nargs="+", choices=["both", "grids_only", "narrative_only"], default=["both"],
                    help="one or more prompt conditions, each run separately (text task only)")
parser.add_argument("--mapping", nargs="+", choices=[COLORS] + list_mappings(), default=[COLORS],
                    help="one or more image mappings from mappings/, each run separately (visual task only)")
parser.add_argument("--models", nargs="+", help="override the task's default model list")
parser.add_argument("--limit", type=int, default=5, help="max samples per model (0 = all)")
parser.add_argument("--max-connections", type=int, default=5, help="concurrent requests per model")
args = parser.parse_args()

# Load OPENAI_BASE_URL and OPENAI_API_KEY from .env
load_dotenv()

BASE_URL = os.getenv("OPENAI_BASE_URL")
API_KEY = os.getenv("OPENAI_API_KEY")

# Fail early with a clear message if .env is missing
if not BASE_URL or not API_KEY:
    raise ValueError("Missing OPENAI_BASE_URL or OPENAI_API_KEY in .env file.")

config = TASKS[args.task]
models = args.models or config["models"]
# The text task varies by --condition, the visual task by --mapping
if args.task == "text":
    variant_name, variants = "condition", list(dict.fromkeys(args.condition))
else:
    variant_name, variants = "mapping", list(dict.fromkeys(args.mapping))
runs = [(model, variant) for model in models for variant in variants]

print(f"Task: {args.task} | limit: {args.limit or 'all'}")
print(f"Models: {', '.join(models)}")
print(f"{variant_name.capitalize()}s: {', '.join(variants)}")
print(f"Total runs: {len(runs)}")
print("(run with -h to see all options)\n")

for i, (model, variant) in enumerate(runs, start=1):
    task_args = {variant_name: variant}
    print(f"({i}/{len(runs)}) Running {args.task} eval for {model} [{variant}]...")
    eval(
        config["task"],
        task_args=task_args,
        model=model,
        model_base_url=BASE_URL,
        model_args={"api_key": API_KEY},
        temperature=0,                        # NARC protocol uses temperature 0
        max_connections=args.max_connections, # Adjust to avoid saturating GPU cluster quotas
        limit=args.limit or None,             # 0 runs the full benchmark
    )
