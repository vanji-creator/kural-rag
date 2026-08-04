"""Every knob of the bake-off, in one place."""

from pathlib import Path

# The package is self-contained: everything lives next to this code.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PACKAGE_ROOT / "data"
PILES_PATH = DATA_DIR / "piles.json"
TEXTS_PATH = DATA_DIR / "texts.json"
BASELINE_PATH = DATA_DIR / "baseline.json"
CHECKPOINT_PATH = DATA_DIR / "checkpoint.json"
RESULTS_PATH = DATA_DIR / "bge_bakeoff_results.json"

# The model under test. 568M parameters, reads 100 languages including
# Tamil, stock architecture - no custom remote code to rot.
MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# How many of the reranked candidates count as "shown to the reader".
TOP_K = 5

# The reranker reads question+verse pairs this many at a time. Bigger is
# faster until the GPU runs out of memory; 16 is safe on a free Colab T4.
BATCH_SIZE = 16

# The longest input the model reads, in tokens (word pieces). Pairs longer
# than this are cut off at the end.
MAX_LENGTH = 512

# Progress is saved to disk after this many questions. A crash or a Colab
# disconnect costs at most this much work.
CHECKPOINT_EVERY = 10

# The two arms: which text of each verse the model reads.
#   english     - the same text the shipping reranker reads (arm A)
#   with_tamil  - that text plus the Tamil meaning
ARMS = [
    ("E: bge english", "english"),
    ("F: bge + tamil text", "with_tamil"),
]
