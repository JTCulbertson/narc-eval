"""Build Inspect AI samples from NARC puzzle JSON files."""
import json
import glob
from pathlib import Path
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, ContentImage, ContentText

from mappings import BASE_DIR, COLORS, legend_text, load_mapping

# Color legend matching the ARC palette used by render_puzzles.py
COLOR_LEGEND = (
    "0 = black, 1 = blue, 2 = red, 3 = green, 4 = yellow, "
    "5 = grey, 6 = magenta, 7 = orange, 8 = light blue, 9 = maroon"
)

def format_grid(grid: list[list[int]]) -> str:
    """Helper to format 2D grid matrix as string representation."""
    return "\n".join(" ".join(str(cell) for cell in row) for row in grid)

def find_puzzles(data_dir: str | Path) -> list[str]:
    """Puzzle JSON files in data_dir, with a clear error if there are none."""
    paths = sorted(glob.glob(f"{data_dir}/*.json"))
    if not paths:
        raise FileNotFoundError(
            f"No puzzle JSON files in {data_dir}/. Add NARC puzzles there "
            "(see examples/example_sunrise.json for the format)."
        )
    return paths


def load_narc_samples(data_dir: str | Path = BASE_DIR / "data", condition: str = "both") -> list[Sample]:
    """
    condition can be:
      - 'both': includes grid sequence + narrative clue
      - 'grids_only': includes grid sequence without narrative
      - 'narrative_only': includes narrative without grid sequence
    """
    samples = []
    json_paths = find_puzzles(data_dir)

    for path in json_paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        puzzle_id = data.get("puzzle_id", Path(path).stem)
        narrative = data.get("narrative", "")
        sequence = data.get("sequence", [])
        masked_positions = data.get("masked_positions", [])
        answer_grids = data.get("answer_grids", {})
        # The missing grids to reconstruct, in masked-position order
        gold_grids = [answer_grids[str(p)] for p in masked_positions]

        # Build prompt depending on condition
        prompt_parts = []
        if condition in ("both", "grids_only"):
            grid_blocks = []
            for step in sequence:
                if step.get("masked") or step.get("grid") is None:
                    grid_blocks.append(f"Position {step['position']}: [MASKED]")
                else:
                    grid_blocks.append(f"Position {step['position']}:\n{format_grid(step['grid'])}")
            prompt_parts.append(
                "Here is the sequence of grids with one or more masked positions:\n\n"
                + "\n\n".join(grid_blocks)
            )
        if condition in ("both", "narrative_only"):
            prompt_parts.append(f"Clue/Narrative:\n{narrative}")

        if len(masked_positions) > 1:
            positions = ", ".join(str(p) for p in masked_positions)
            instruction = (
                f"\nYour task is to reconstruct the masked grids (positions {positions}). "
                "Output one JSON matrix [[...], [...]] per masked position, in position order, "
                "with no extra conversation."
            )
        else:
            instruction = (
                "\nYour task is to reconstruct the masked grid. "
                "Output your final reconstructed grid as a JSON matrix [[...], [...]] "
                "with no extra conversation."
            )
        prompt_parts.append(instruction)

        prompt = "\n\n".join(prompt_parts)
        target_str = json.dumps(gold_grids)

        samples.append(
            Sample(
                input=prompt,
                target=target_str,
                id=puzzle_id,
                metadata={
                    "puzzle_id": puzzle_id,
                    "condition": condition,
                    "masked_positions": masked_positions,
                    "gold_grids": gold_grids
                }
            )
        )
    return samples


def load_narc_visual_samples(data_dir: str | Path = BASE_DIR / "data", image_dir: str | Path = BASE_DIR / "images", mapping: str = COLORS) -> list[Sample]:
    """
    Visual variant: the model sees the rendered puzzle image (title, narrative and
    grid sequence with masked positions shown as '?') instead of text grids.
    Images are produced by render_puzzles.py and matched to the JSON by filename.

    mapping: 'colors' uses the colour images in image_dir. Any other name is a pattern
    mapping from mappings/, read from greyscale_images/<mapping>/.
    """
    if mapping == COLORS:
        grid_desc, legend = "colored grids", f"Each cell color corresponds to an integer: {COLOR_LEGEND}."
    else:
        image_dir = BASE_DIR / "greyscale_images" / mapping
        grid_desc = "black-and-white patterned grids"
        legend = f"Each cell pattern corresponds to an integer: {legend_text(load_mapping(mapping))}."

    samples = []
    json_paths = find_puzzles(data_dir)

    for path in json_paths:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        image_path = Path(image_dir) / f"{Path(path).stem}.png"
        if not image_path.exists():
            render_cmd = "render_puzzles.py" if mapping == COLORS else f"render_puzzles.py --mapping {mapping}"
            raise FileNotFoundError(f"Missing {image_path}; run {render_cmd} first.")

        puzzle_id = data.get("puzzle_id", Path(path).stem)
        masked_positions = data.get("masked_positions", [])
        answer_grids = data.get("answer_grids", {})
        gold_grids = [answer_grids[str(p)] for p in masked_positions]

        if len(masked_positions) > 1:
            positions = ", ".join(str(p) for p in masked_positions)
            instruction = (
                f"Your task is to reconstruct the masked grids (positions {positions}). "
                "Output one JSON matrix [[...], [...]] per masked position, in position order, "
                "with no extra conversation."
            )
        else:
            instruction = (
                "Your task is to reconstruct the masked grid. "
                "Output your final reconstructed grid as a JSON matrix [[...], [...]] "
                "with no extra conversation."
            )

        prompt = (
            f"The image shows a puzzle: a title, a narrative clue, and a sequence of {grid_desc}. "
            "Masked positions are shown as grey boxes with a '?', drawn at the same size as the "
            "grid they hide.\n\n"
            f"{legend}\n\n"
            + instruction
        )

        samples.append(
            Sample(
                input=[
                    ChatMessageUser(content=[
                        ContentImage(image=str(image_path.resolve())),
                        ContentText(text=prompt),
                    ])
                ],
                target=json.dumps(gold_grids),
                id=puzzle_id,
                metadata={
                    "puzzle_id": puzzle_id,
                    "condition": "visual",
                    "mapping": mapping,
                    "masked_positions": masked_positions,
                    "gold_grids": gold_grids
                }
            )
        )
    return samples
