"""The same question rewriter, run by llama.cpp instead of transformers.

WHY A SECOND VERSION EXISTS

src/hyde.py works and is unusably slow: 15 words in 16 seconds, about one word
per second. A 1.7B model on 8 cores should manage ten to twenty.

Capping the output proved the time was not in generation - allowing 60 words,
32 or 24 all took the same 16 seconds, because the model was already stopping
at 15. So the cost is per-word overhead, not word count.

The reason is what `transformers` is for. It is built for TRAINING: flexible,
general, and carrying machinery we never use. That is the right trade for our
reranker, which does one pass over 50 pairs and stops. It is the wrong trade
for generating text, which runs the whole model once per word - fifteen times
here, each paying that overhead again.

llama.cpp does nothing but that loop, in C++, compiled against the exact
instruction set this processor has.

NO QUANTIZATION

The weights are BF16 - bit for bit what Qwen published. GGUF is a file layout,
not a compression. The Q8_0 file offered on the model page IS an 8-bit squeeze
and is deliberately not used (CLAUDE.md 3.5).

Run it:

    venv/bin/python src/hyde_fast.py "how do I keep my temper?"
"""

import sys
import time

from huggingface_hub import hf_hub_download
from llama_cpp import Llama

from hyde import INSTRUCTION, MAX_NEW_TOKENS

GGUF_REPO = "unsloth/Qwen3-1.7B-GGUF"
GGUF_FILE = "Qwen3-1.7B-BF16.gguf"

# This machine has 8 real cores. Counting the 8 hyperthreads as well usually
# makes CPU inference slower, not faster - they share the same arithmetic
# units, so two threads on one core just take turns.
CPU_THREADS = 8

# The prompt is about 210 tokens and the answer is about 15. 512 is plenty,
# and a smaller window means less memory reserved for nothing.
CONTEXT_TOKENS = 512


class FastHydeRewriter:
    """Loads the model ONCE and rewrites questions with it."""

    def __init__(self):
        print(f"downloading/locating {GGUF_FILE}...")
        model_path = hf_hub_download(GGUF_REPO, GGUF_FILE)
        print(f"loading with llama.cpp on {CPU_THREADS} threads...")
        self.model = Llama(model_path=model_path,
                           n_ctx=CONTEXT_TOKENS,
                           n_threads=CPU_THREADS,
                           verbose=False)

    def rewrite(self, question):
        """One question in, one answer-shaped statement out."""
        response = self.model.create_chat_completion(
            messages=[{"role": "system", "content": INSTRUCTION},
                      {"role": "user", "content": f"question: {question}"}],
            max_tokens=MAX_NEW_TOKENS,
            temperature=0.0,  # same question -> same rewrite, every time
        )
        text = response["choices"][0]["message"]["content"].strip()

        # Qwen3 can still emit a <think> block; drop it if it appears.
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
        text = text.split("\n")[0].strip()
        if text.lower().startswith("statement:"):
            text = text[len("statement:"):].strip()
        return text or question


def main():
    # Deliberately NOT the questions used as examples inside INSTRUCTION -
    # the first test was rigged that way and the model simply copied them.
    questions = sys.argv[1:] or [
        "how do I keep my temper?",
        "my friend disappears whenever I need something",
        "I open my laptop and end up doing nothing for hours",
        "should I spend time with people better than me?",
        "the whole neighbourhood is talking about us",
    ]

    rewriter = FastHydeRewriter()
    print()
    times = []
    for question in questions:
        started_at = time.perf_counter()
        statement = rewriter.rewrite(question)
        elapsed = time.perf_counter() - started_at
        times.append(elapsed)
        print(f"  {question}")
        print(f"    -> {statement}")
        print(f"       ({elapsed:.1f} s)")
        print()

    print(f"average {sum(times) / len(times):.1f} s per question")
    print(f"transformers was 16.7 s - this is "
          f"{16.7 / (sum(times) / len(times)):.1f}x faster")


if __name__ == "__main__":
    main()
