"""The reranker model, wrapped so the rest of the code never touches it.

Loads with plain transformers, not the sentence-transformers wrapper. That
wrapper silently mis-loads this exact model's scoring head and returns
0.000 for every pair - no error, just a ranking made of noise. Found the
hard way in the main project (src/rerank.py tells the story).

Runs on the GPU when one is there, on the CPU when not. Same numbers either
way - just a very different wait.
"""

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from . import config


class Reranker:
    def __init__(self, model_name=config.MODEL_NAME):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"loading {model_name} on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name)
        self.model.to(self.device)
        self.model.eval()

    def score_pairs(self, question_text, verse_texts):
        """One score per verse text. Higher = answers the question better.

        Raw model outputs on the model's own scale - only their ORDER means
        anything. Scored in batches so a long pile cannot run the GPU out
        of memory.
        """
        scores = []
        for start in range(0, len(verse_texts), config.BATCH_SIZE):
            batch = verse_texts[start:start + config.BATCH_SIZE]
            pairs = [[question_text, verse_text] for verse_text in batch]
            with torch.no_grad():
                tokenized = self.tokenizer(pairs, padding=True,
                                           truncation=True,
                                           return_tensors="pt",
                                           max_length=config.MAX_LENGTH)
                tokenized = {name: tensor.to(self.device)
                             for name, tensor in tokenized.items()}
                logits = self.model(**tokenized).logits.view(-1).float()
            scores.extend(logits.cpu().tolist())
        return scores
