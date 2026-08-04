"""Progress that survives crashes, disconnects and hot laptops.

Learned the hard way, twice in this project: a run that saves only at the
end costs you everything when it stops early. Here, scores go to disk every
few questions, and the write is ATOMIC - the new file is written beside the
old one and swapped in one step, so even a crash in the middle of saving
cannot leave a half-written file behind.
"""

import json
import os

from . import config


def load_checkpoint():
    """Whatever an earlier, interrupted run already scored. {} if nothing."""
    if not config.CHECKPOINT_PATH.exists():
        return {}
    try:
        with open(config.CHECKPOINT_PATH, encoding="utf-8") as open_file:
            return json.load(open_file)
    except json.JSONDecodeError:
        # Should be impossible given atomic writes; refuse to guess if it
        # happens anyway.
        raise SystemExit(
            f"{config.CHECKPOINT_PATH} is corrupt. Delete it to start the "
            "run over, or restore it from a copy.")


def save_checkpoint(checkpoint):
    """Write the checkpoint so that no crash can corrupt it."""
    temporary_path = config.CHECKPOINT_PATH.with_suffix(".tmp")
    with open(temporary_path, "w", encoding="utf-8") as open_file:
        json.dump(checkpoint, open_file)
        open_file.flush()
        os.fsync(open_file.fileno())
    os.replace(temporary_path, config.CHECKPOINT_PATH)
