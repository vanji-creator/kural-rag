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


# ----------------------------------------------------------------------
# The same job, aimed at a MODERN corpus (added 2026-08-03)
# ----------------------------------------------------------------------
#
# The instruction above tells the model to reach for "formal or old-fashioned
# words". That was right, and measured, while the only English in the corpus
# was an 1880s translation: the question had to travel to where the text was.
#
# We then rewrote the corpus into plain modern English. Pointing the question
# at archaic vocabulary that the text no longer contains is now working
# against ourselves - we would be searching for "avarice" in a document that
# says "greed".
#
# WHAT DELIBERATELY DOES NOT CHANGE
#
# The core of HyDE stays: turn the question into a STATEMENT of what the
# answer would say, and name the underlying subject rather than the person's
# surface situation. That is what stopped kural 251 - a verse about eating
# meat - from answering 26 of our first 100 questions purely because it is
# phrased as a question. Only the vocabulary instruction moves.
#
# The examples are the same cars/code/plumbing ones for the same reason: they
# share no subject matter with Thirukkural, so no model can score by copying
# them. A different set of examples here would make any comparison between
# the two prompts partly a comparison of their examples.

INSTRUCTION_MODERN = """You rewrite search queries. The search is over a book \
of short verses about how to live: virtue, wealth, work, friendship, \
rulership and love. The verses are explained in plain modern English.

Rewrite the user's question as a short STATEMENT describing what the answer \
would say. Never answer as a question.

Two rules:
- Name the underlying subject, not the surface details of the person's situation.
- Use the plain words a clear modern explanation of that subject would use.

Reply with the statement only. No explanation. One line. Under 20 words.

Examples:
question: my car makes a grinding noise when I brake
statement: worn brake pads, damaged discs, metal rubbing on metal in the \
braking system

question: my code gets really slow once the list is big
statement: the method does not scale, it repeats work, it slows down as the \
data grows

question: water is coming up through the shower drain
statement: a blocked waste pipe, water flowing back up, something stuck in \
the drain"""


# ----------------------------------------------------------------------
# Examples from THIS book's world (added 2026-08-03, Vikash's suggestion)
# ----------------------------------------------------------------------
#
# Both instructions above teach with cars, code and plumbing. That was a
# deliberate choice and it was right for ONE job: measuring. A model given an
# anger example can reproduce it for an anger question and score a point
# without having understood anything - Qwen3-0.6B did exactly that.
#
# But that protects a measurement, not a user. In production nobody checks
# whether the model understood; they want the best rewrite. And an example
# drawn from the same world as the corpus shows the model what a good answer
# here actually looks like. That is ordinary few-shot prompting and it usually
# wins.
#
# Vikash's question: "am i correct or were u correct by giving out of context
# ones". Both, about different things. So it gets measured.
#
# TWO CONTROLS, BECAUSE IN-DOMAIN EXAMPLES ARE HOW LEAKAGE HAPPENS
#
# 1. None of these example QUESTIONS may resemble a question in the 233-item
#    test set. "How do I control my anger" is literally question 1 of the
#    golden set; using it here would be the fourth leakage incident in this
#    project. src/check_prompt_leakage.py measures the overlap rather than
#    trusting this paragraph.
#
# 2. The example STATEMENTS are added to EXAMPLE_STATEMENTS below, so the
#    copying check catches a model that parrots them instead of thinking.

INSTRUCTION_IN_DOMAIN = """You rewrite search queries. The search is over a \
book of short verses about how to live: virtue, wealth, work, friendship, \
rulership and love. The verses are explained in plain modern English.

Rewrite the user's question as a short STATEMENT describing what the answer \
would say. Never answer as a question.

Two rules:
- Name the underlying subject, not the surface details of the person's situation.
- Use the plain words a clear modern explanation of that subject would use.

Reply with the statement only. No explanation. One line. Under 20 words.

Examples:
question: the man who lent me money when I had nothing now needs help himself
statement: gratitude, repaying a kindness received, remembering help given in \
hard times

question: my business partner keeps promising things and never delivers
statement: broken promises, failing to keep one's word, unreliable conduct in \
an agreement

question: I inherited a large sum and I do not know what to do with it
statement: using wealth well, spending it on worthy things, wasting an \
inheritance"""


# ----------------------------------------------------------------------
# A SECOND rewrite, aimed at the chapter descriptions (2026-08-04)
# ----------------------------------------------------------------------
#
# Every rewrite above is compared against TWO different kinds of text:
#
#     133 chapter descriptions   ~44 words, a topic summary plus a word list
#    1330 verse texts            ~47 words, a verse plus its meaning
#
# One rewrite has to be a good match for both, and it cannot be. A verse says
# what happens in one situation; a chapter description says what an area of
# life is about. Those are different shapes of text, and an embedding is
# sensitive to shape as well as subject.
#
# So the question gets rewritten TWICE - once shaped like a verse meaning,
# once shaped like a chapter description - and each is compared against the
# thing it was shaped for.
#
# This is HyDE's own logic applied a second time. HyDE exists because a
# QUESTION and an ANSWER are written differently, so searching with a
# question finds other questions. The same argument says searching a topic
# summary with an answer-shaped sentence finds the wrong kind of thing.
#
# WHY THIS IS WORTH THE SECOND CALL
#
# Reading the 8 questions the modern corpus fixed, every one was fixed the
# same way: the right CHAPTER was found. "how do I stop being scared of
# speaking in public" reached the chapter literally called "Not to dread the
# Council" - which the old corpus missed entirely. The chapter match is doing
# the work, so it is worth aiming at directly.
#
# Cost: one extra call, about Rs 0.00125 per question, and no extra waiting
# if the two run at the same time.

INSTRUCTION_CHAPTER = """You rewrite a question into a description of the \
SUBJECT AREA it belongs to.

The search is over a book about how to live, divided into 133 short chapters. \
Each chapter covers one subject - things like restraining anger, choosing \
friends, farming, the duties of a ruler, or the sulking of lovers.

You are NOT answering the question. You are describing the area of life the \
question belongs to, the way a chapter heading and summary would.

Write it in this shape:

- One sentence naming the subject area in plain modern English.
- Then a list of words connected to that subject: everyday words a person \
would use, and the formal words a book would use, together.

Reply with the sentence and the word list only. No explanation. Under 40 \
words.

Examples:
question: the man who lent me money when I had nothing now needs help himself
statement: Returning help to someone who helped you first. gratitude, \
thankfulness, repaying kindness, obligation, indebtedness, remembering a \
favour, ingratitude

question: my business partner keeps promising things and never delivers
statement: Keeping your word once you have given it. promises, agreements, \
reliability, trustworthiness, breaking faith, going back on your word, \
dependability

question: I inherited a large sum and I do not know what to do with it
statement: What wealth is for and how it should be used. wealth, riches, \
money, giving, generosity, spending, hoarding, waste, charity, inheritance"""

# Which one the pipeline uses. This is the second rollback switch, alongside
# CORPUS_TEXT_MODE in pipeline.py - and the two belong together. An archaic
# prompt against a modern corpus, or the reverse, is a mismatch on purpose
# only when we are measuring it.
#
#   "classic"    reach for old-fashioned words  - matches CORPUS_TEXT_MODE classic
#   "modern"     plain modern words, out-of-domain examples
#   "in-domain"  plain modern words, examples from this book's world
#
# Tried "modern" on 2026-08-04 (Vikash's call, measured by
# src/measure_requested_settings.py): 164/233 against 174, and a REAL loss on
# Set A (89 vs 97, p = 0.0215). Why it lost: the classic instruction asks for
# the old words ALONGSIDE the everyday ones, so its rewrites carry both
# vocabularies. The modern one carries only half. Rolled back same day.
PROMPT_MODE = "classic"

_INSTRUCTIONS = {
    "classic": INSTRUCTION,
    "modern": INSTRUCTION_MODERN,
    "in-domain": INSTRUCTION_IN_DOMAIN,
    # Shaped like a chapter description, not like a verse. Used for the
    # chapter half of the score only - see the note above.
    "chapter": INSTRUCTION_CHAPTER,
}


def instruction_for(mode=None):
    """The rewrite instruction to use. One place decides, so nothing drifts."""
    mode = mode or PROMPT_MODE
    if mode not in _INSTRUCTIONS:
        raise ValueError(f"unknown prompt mode {mode!r}. "
                         f"known: {', '.join(_INSTRUCTIONS)}")
    return _INSTRUCTIONS[mode]


# The example QUESTIONS, kept separately so the leakage check can compare them
# against the 233 test questions without re-parsing the instructions.
EXAMPLE_QUESTIONS = [
    "my car makes a grinding noise when I brake",
    "my code gets really slow once the list is big",
    "water is coming up through the shower drain",
    "the man who lent me money when I had nothing now needs help himself",
    "my business partner keeps promising things and never delivers",
    "I inherited a large sum and I do not know what to do with it",
]

# The chapter-aimed prompt reuses the same three example questions on purpose.
# Different examples would make any comparison between it and the in-domain
# prompt partly a comparison of their examples.

# Sentences a model could copy from EITHER instruction. Any output that
# matches one is mimicry rather than comprehension, and the benchmark flags
# it. Both prompts' examples are listed because a model given the modern
# prompt could still parrot it.
EXAMPLE_STATEMENTS = [
    "worn brake pads, damaged discs, metal rubbing on metal in the braking system",
    "the method does not scale, it repeats work, it slows down as the data grows",
    "a blocked waste pipe, water flowing back up, something stuck in the drain",
    "gratitude, repaying a kindness received, remembering help given in hard times",
    "broken promises, failing to keep one's word, unreliable conduct in an agreement",
    "using wealth well, spending it on worthy things, wasting an inheritance",
    "Returning help to someone who helped you first.",
    "Keeping your word once you have given it.",
    "What wealth is for and how it should be used.",
    "worn brake pads, scored rotors, metal-on-metal friction in the braking system",
    "poor algorithmic complexity, inefficient iteration, performance degradation at scale",
    "blocked waste pipe, drainage backflow, obstruction in the soil stack",
]

MAX_NEW_TOKENS = 60
