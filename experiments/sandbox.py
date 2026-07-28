from sentence_transformers import SentenceTransformer

# load the multilingual model (downloads once, then cached)
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# how many dimensions does each vector have?
print("dimensions:", model.get_sentence_embedding_dimension())

# some sentences: English, Tamil, Thanglish, and one unrelated
sentences = [
    "how to control anger",          # 0  English
    "சினம் அடக்குவது எப்படி",          # 1  Tamil (same meaning)
    "sinam adakkuvadhu eppadi",       # 2  Thanglish (same meaning)
    "best price for used cars",       # 3  unrelated
]

# turn each sentence into a 384-number vector
embeddings = model.encode(sentences)

print("shape:", embeddings.shape)   # (4 sentences, 384 numbers each)

# cosine similarity BY HAND — no library shortcut
import numpy as np

def cosine_similarity(vector_a, vector_b):
    dot_product = np.dot(vector_a, vector_b)
    length_a = np.linalg.norm(vector_a)
    length_b = np.linalg.norm(vector_b)
    return dot_product / (length_a * length_b)

# compare sentence 0 (English) against every sentence
english_anger = embeddings[0]
for index, sentence in enumerate(sentences):
    score = cosine_similarity(english_anger, embeddings[index])
    print(f"{score:.3f}   vs  [{index}] {sentence}")