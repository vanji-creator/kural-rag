"""Load the frozen data and refuse to run if anything disagrees.

Every check here exists to fail in the first second, on the CPU, with a
plain message - instead of failing forty GPU-minutes in, or worse, running
to completion on wrong data and producing a confident wrong table.
"""

import json

from . import config


class BadPackage(Exception):
    """The data files do not agree with each other. Do not compute."""


def load_and_validate():
    """Returns (piles, texts, baseline, set_a_size), or raises BadPackage."""
    for path in (config.PILES_PATH, config.TEXTS_PATH, config.BASELINE_PATH):
        if not path.exists():
            raise BadPackage(f"missing data file: {path}. "
                             "Unzip the package with its data/ folder intact.")

    with open(config.PILES_PATH, encoding="utf-8") as open_file:
        piles_file = json.load(open_file)
    with open(config.TEXTS_PATH, encoding="utf-8") as open_file:
        texts = json.load(open_file)
    with open(config.BASELINE_PATH, encoding="utf-8") as open_file:
        baseline = json.load(open_file)

    piles = piles_file["questions"]
    set_a_size = piles_file["set_a_size"]

    if not piles:
        raise BadPackage("piles.json holds no questions.")

    if len(baseline["top5"]) != len(piles):
        raise BadPackage(
            f"baseline covers {len(baseline['top5'])} questions but there "
            f"are {len(piles)} piles. These came from different runs.")

    pile_sizes = {len(entry["pile"]) for entry in piles}
    if len(pile_sizes) != 1:
        raise BadPackage(f"piles are not all the same size: {pile_sizes}")

    # Every verse any pile mentions must have both of its texts present.
    for entry in piles:
        for number in entry["pile"]:
            record = texts.get(str(number))
            if record is None:
                raise BadPackage(f"kural {number} is in a pile but has no "
                                 "text in texts.json.")
            if not record.get("english") or not record.get("with_tamil"):
                raise BadPackage(f"kural {number} has an empty text.")

    # The known shape of the frozen record, stated in the export script.
    reachable = sum(1 for entry in piles
                    if set(entry["pile"]) & set(entry["correct"]))
    print(f"loaded {len(piles)} questions "
          f"(set A: {set_a_size}), pile size {pile_sizes.pop()}, "
          f"{reachable} reachable, baseline arm: {baseline['label']}")
    return piles, texts, baseline, set_a_size
