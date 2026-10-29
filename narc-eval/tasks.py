"""Inspect AI task definitions for the NARC eval (text and visual variants)."""
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate, system_message
from utils import load_narc_samples, load_narc_visual_samples
from scorers import narc_grid_scorer

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

SYSTEM_PROMPT = (
    "You are an expert abstract reasoning assistant evaluating visual and narrative clues. "
    "Carefully analyze the spatial transitions and narrative semantics."
)

@task
def narc_eval(condition: str = "both"):
    """
    Run NARC evaluation.
    Can be configured via CLI parameter: -T condition=grids_only / narrative_only / both
    """
    dataset = load_narc_samples(data_dir=DATA_DIR, condition=condition)
    
    return Task(
        dataset=dataset,
        solver=[
            system_message(SYSTEM_PROMPT),
            generate()
        ],
        scorer=narc_grid_scorer()
    )

@task
def narc_eval_visual(mapping: str = "colors"):
    """
    Run NARC evaluation on rendered puzzle images (see render_puzzles.py).
    Requires a vision-capable model.
    Can be configured via CLI parameter: -T mapping=<name from mappings/> (default: colors)
    """
    dataset = load_narc_visual_samples(data_dir=DATA_DIR, image_dir=BASE_DIR / "images", mapping=mapping)

    return Task(
        dataset=dataset,
        solver=[
            system_message(SYSTEM_PROMPT),
            generate()
        ],
        scorer=narc_grid_scorer()
    )
