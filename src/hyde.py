"""Turn a question into the shape of an ANSWER before searching.

THE PROBLEM THIS SOLVES

Our verses are answers. A user types a question. Those two things are written
differently, and the search model notices the difference.

Measured proof: kural 251 is about eating meat, and it answered 26 of our 100
questions. Why? Because it opens "What graciousness can one command..." - it is
phrased as a question, and so were our queries. The model matched question
shape to question shape and ignored the subject entirely.

THE FIX

Ask a language model to rewrite the question as a short statement of what the
answer would look like:

    "how do I control my anger?"   ->   "restraining anger and controlling
                                        wrath, keeping calm when provoked"

Now we are comparing an answer-shaped string against answer-shaped verses.

This is a published technique called HyDE - Hypothetical Document Embeddings.
The idea in one line from the literature: "a hypothetical answer shares the
vocabulary, length and structure of real answers, so its nearest neighbours are
real answers rather than other similarly-phrased questions."

THE SECOND THING IT BUYS

Our corpus is a 19th-century English translation. It says sloth, wrath, ire,
penury, council. A reader says lazy, anger, poor, public speaking. A language
model knows both, so the rewrite can carry the old words in - which plain word
deletion can never do.

Seven of our fifteen remaining failures are exactly that gap.

Run it:

    venv/bin/python src/hyde.py "how do I control my anger?"
"""

import sys
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Chosen for four reasons, in order:
#   1. Apache 2.0 licence - no restrictions on use at all. Gemma and Llama
#      both attach their own rules.
#   2. It fits. 3.4 GB in memory, against ~9 GB free with the search models
#      loaded. The 4B version needs 8.0 GB and does NOT fit.
#   3. Nothing is rounded. No quantization (CLAUDE.md 3.5).
#
#      Worth being exact about what that means here. This model's weights are
#      STORED as bfloat16 - 2 bytes per number. That is not a compressed copy,
#      it is the model. Loading it as float32 would copy each number into a
#      4-byte box and leave the extra space empty: 6.9 GB instead of 3.4 GB,
#      for identical answers.
#
#      Quantization is squeezing weights DOWN to 8 or 4 bits, which loses real
#      information. We are not doing that. Loading at the model's own precision
#      is the full-accuracy choice, not a compromise.
#   4. Best multilingual prospects for the Tamil work still open - though NO
#      candidate model declares Tamil in its metadata, so that is a hope and
#      not a fact until measured.
MODEL_NAME = "Qwen/Qwen3-1.7B"

# The rewrite is one short line. Anything longer is the model rambling, and a
# long hypothetical answer drifts away from the topic.
MAX_NEW_TOKENS = 60

INSTRUCTION = """You rewrite search queries for a search over Thirukkural, an \
ancient Tamil book of 1330 short verses on virtue, wealth and love.

Rewrite the user's question as a short STATEMENT describing what the answer \
would say. Never answer as a question.

Include older or more formal words that a 19th-century English translation \
would use, alongside the everyday word.

Reply with the statement only. No explanation. One line. Under 20 words.

Examples:
question: how do I control my anger?
statement: restraining anger, curbing wrath and ire, staying calm when provoked

question: how do I stop being lazy?
statement: avoiding sloth and idleness, unsluggishness, industry and steady effort

question: how do I know if she likes me back?
statement: reading the signs of a woman's love, glances and looks that reveal \
her feelings"""


class HydeRewriter:
    """Loads the language model ONCE and rewrites questions with it."""

    def __init__(self, model_name=MODEL_NAME):
        print(f"loading {model_name} at its own precision (bfloat16)...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        # dtype="auto" loads the weights exactly as the model stores them.
        # Nothing is rounded down, and nothing is padded up.
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, dtype="auto")
        self.model.eval()

    def rewrite(self, question):
        """One question in, one answer-shaped statement out."""
        messages = [{"role": "system", "content": INSTRUCTION},
                    {"role": "user", "content": f"question: {question}"}]

        # Qwen3 writes out its reasoning before answering unless told not to.
        # For a one-line rewrite that reasoning is pure cost, so it is off.
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)

        inputs = self.tokenizer([prompt], return_tensors="pt")
        with torch.no_grad():
            generated = self.model.generate(
                **inputs, max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,  # same question -> same rewrite, every time
                pad_token_id=self.tokenizer.eos_token_id)

        new_tokens = generated[0][len(inputs.input_ids[0]):]
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)

        # Strip a "statement:" prefix if the model echoes the example format,
        # and keep only the first line.
        text = text.strip().split("\n")[0].strip()
        if text.lower().startswith("statement:"):
            text = text[len("statement:"):].strip()
        return text or question  # never return nothing


def main():
    questions = sys.argv[1:] or [
        "how do I control my anger?",
        "how do I stop being lazy?",
        "how do I keep my temper?",
        "should I spend time with people better than me?",
        "what happens when people start gossiping about lovers?",
    ]

    rewriter = HydeRewriter()
    print()
    for question in questions:
        started_at = time.perf_counter()
        statement = rewriter.rewrite(question)
        elapsed = time.perf_counter() - started_at
        print(f"  {question}")
        print(f"    -> {statement}")
        print(f"       ({elapsed:.1f} s)")
        print()


if __name__ == "__main__":
    main()
