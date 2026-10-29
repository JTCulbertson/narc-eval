"""Exact-match scorer: the model's final grid(s) must equal the hidden answer grid(s)."""
import json
import re
from inspect_ai.scorer import scorer, Score, Target, accuracy, stderr
from inspect_ai.solver import TaskState

def extract_grids_from_text(text: str):
    """Simple extractor: returns every JSON 2D array [[...], [...]] found in the text."""
    grids = []
    for match in re.findall(r"(\[\[.*?\]\])", text, re.DOTALL):
        try:
            grids.append(json.loads(match))
        except Exception:
            pass
    return grids

@scorer(metrics=[accuracy(), stderr()])
def narc_grid_scorer():
    async def score(state: TaskState, target: Target):
        model_output = state.output.completion
        gold_grids = state.metadata.get("gold_grids", [])

        # Use the last N grids so earlier working / restated inputs are ignored
        extracted = extract_grids_from_text(model_output)
        predicted_grids = extracted[-len(gold_grids):] if gold_grids else []

        is_correct = len(gold_grids) > 0 and predicted_grids == gold_grids

        return Score(
            value=1.0 if is_correct else 0.0,
            answer=json.dumps(predicted_grids),
            explanation=f"Predicted: {predicted_grids} | Target: {gold_grids}"
        )
    return score
