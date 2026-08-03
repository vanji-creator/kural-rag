"""The rewrite instruction, written so a model cannot pass by copying it.

WHY THIS FILE EXISTS SEPARATELY

The first version of this instruction used worked examples about anger, laziness
and love - the same subjects Thirukkural covers. Qwen3-0.6B then produced, for
"how do I keep my temper?":

    restraining anger, curbing wrath and ire, staying calm when provoked

which is one of those examples word for word. It scored a point for "bridging
vocabulary" while having bridged nothing. It also glued the word "restraining"
onto the front of every unrelated answer, including "restraining the friend's
disappearance", which is not English.

An automatic check that counts "did a corpus word appear" cannot tell
understanding from copying. Both score.

THE FIX

The examples below teach the FORMAT and the BEHAVIOUR - turn a question into a
statement, and reach for the words an expert would use - while sharing no
subject matter with Thirukkural at all. Cars, code, plumbing. There is no
sentence here a model could copy that would help it answer a question about
virtue, friendship, poverty or love.

That separates the two abilities we care about:

    following a format   - taught by the examples, fair to both models
    bridging vocabulary  - NOT taught here, must come from the model itself
"""

INSTRUCTION = """You rewrite search queries. The search is over a book of \
short verses about how to live: virtue, wealth, work, friendship, rulership \
and love. It was written long ago and translated into old-fashioned English.

Rewrite the user's question as a short STATEMENT describing what the answer \
would say. Never answer as a question.

Two rules:
- Name the underlying subject, not the surface details of the person's situation.
- Include the formal or old-fashioned words an expert would use for that \
subject, alongside the everyday word.

Reply with the statement only. No explanation. One line. Under 20 words.

Examples:
question: my car makes a grinding noise when I brake
statement: worn brake pads, scored rotors, metal-on-metal friction in the \
braking system

question: my code gets really slow once the list is big
statement: poor algorithmic complexity, inefficient iteration, performance \
degradation at scale

question: water is coming up through the shower drain
statement: blocked waste pipe, drainage backflow, obstruction in the soil stack"""

# Sentences a model could copy from the instruction. Any output that matches
# one of these is mimicry, not comprehension, and the benchmark flags it.
EXAMPLE_STATEMENTS = [
    "worn brake pads, scored rotors, metal-on-metal friction in the braking system",
    "poor algorithmic complexity, inefficient iteration, performance degradation at scale",
    "blocked waste pipe, drainage backflow, obstruction in the soil stack",
]

MAX_NEW_TOKENS = 60
