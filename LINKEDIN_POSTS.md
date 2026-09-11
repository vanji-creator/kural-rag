# LinkedIn posts — Kural RAG

Two posts, spaced 4–6 days. English. Video on post 1, screenshot on post 2.
Nothing clickable: the repo is private and the app is not hosted.

**Every number below is traced to `PROJECT_UNIVERSE.md` §12.1 (the
safe-to-claim table). Do not add a number that is not in that table.**

---

## Before you read the drafts: a thing that exists already

**`thirukural.ai` is live.** Built by a team under Suresh Sambandam (CEO of
Kissflow, convenor of Dream Tamilnadu), on GPT-4 with RAG. English, Tamil
and Thanglish input. Launched at the KaniTamil24 conference and reportedly
passed 100,000 users in a single day.

This is not a reason to stop. It is a reason to be precise. If you post as
if you invented the idea, someone will link it in the comments within an
hour, and that comment becomes your post.

So:

- **Never claim this is the first or the only one.** It is not.
- **Do claim what is actually yours: the measurement.** Anyone can wire a
  retrieval system to GPT-4 in a weekend. Almost nobody writes 100 test
  questions by hand, checks the answer key verse by verse, and then reports
  that their own idea lost ground with a p-value attached. That is your
  post 2, and it is the honest reason to hire you.
- **Check before you post** whether they publish retrieval numbers. If they
  do, read them. If they don't, do not say so in the post — just let your
  own numbers speak. Never say "they don't measure"; you cannot know that.

If someone raises it in the comments, the reply is prepared and friendly:

> Yes — thirukural.ai got there first and got there big. Mine is a smaller,
> slower thing built to answer a different question: how do you *prove* a
> retrieval system got the right verse? That's the part I've been measuring.
> Happy to share what I found.

---

# POST 1 — the story

**Goal:** get watched and shared. Tamil groups, general feed.
**Attach:** the 40–60 s video (shot list below).

---

A text written 2,000 years ago has no word for "laptop."

I asked it why I lose whole days to mine. It answered — and it was right.

I built **Kural RAG**. You ask a question in plain English, Tamil, or
Thanglish. It finds the Thirukkural verses that actually answer it, then
writes a short answer where **every sentence carries the number of the
verse it came from**.

Here is the part I did not expect.

Ordinary search is useless here. Search 1330 classical Tamil verses for
"laptop" and you get nothing — the word does not exist in that text and
never will. So before searching, the system rewrites the question into the
words the text itself would use: *idleness, wasted days, delay, inaction.*
Then it searches for those.

That single step is why an English question can find a Tamil verse that
shares no words with it at all.

Where it stands today, measured on 233 test questions I wrote by hand:

→ a correct verse appears in the 5 shown — **78% of the time**
→ the very first verse shown is correct — **56% of the time**

That second number is the one demos usually leave out. I am including it
because it is the one I am still working on.

The text itself comes from volunteers at **Project Madurai**, who typed the
Thirukkural into the public domain decades before anyone needed it for
this. The question-rewriting and the final answer run on **Sarvam AI**'s
model — about half a paisa per question.

Not hosted yet. Runs on my laptop for now.

**If you could ask a 2,000-year-old book one question, what would it be?**
Put it below. I will run the good ones and post what it says. 👇

`#Thirukkural #Tamil #RAG #LLM #InformationRetrieval #SarvamAI #IndicNLP
#MachineLearning`

---

**Why the last line is there:** with no link to click, the comments are the
only thing that can carry this post. A question anyone can answer in four
words is the strongest tool you have. It also hands you post 3 for free.

---

# POST 2 — the engineering

**Goal:** make an ML hiring manager stop scrolling.
**Post:** 4–6 days after post 1. Same morning slot.
**Attach:** one clean screenshot — the scorecard table, or the pipeline
animation frozen mid-stage.

---

My retrieval was correct 44 times out of 100. It is now 97.

Nothing clever did that. Measuring did.

Last week I posted a thing that answers questions from the Thirukkural.
This is the unglamorous half — how I know it works.

**First I built the ruler, not the model.**

100 questions, written by hand. For each one, the verse numbers a human
decided were correct — including verses from other chapters, checked one at
a time. 200 of those hand-checks.

The uncomfortable part: if that answer key is wrong, a correct system gets
marked wrong and you never find out. The key is the experiment.

**Then one change at a time, 44 → 97.**

The biggest single jump — 44 to 69 — came from **deleting** words. Not
adding a model. Removing the question words themselves. "What does the
Thirukkural say about..." appears in every question, so it distinguishes
nothing, and it was drowning the words that mattered.

No information was added. Noise was removed.

**Then a result that told me I was wrong.**

The system picks 50 candidate verses, then reranks them to choose 5. I
assumed the search was the weak part, so I widened the pile from 50 to 75.
More correct verses reached the reranker — and the final results got
**worse** (p = 0.0352).

That is the whole lesson. Counting what reaches a stage tells you nothing
about whether that stage uses it. Only changing the stage tells you. The
widening did not fix the bottleneck; it proved where the bottleneck was.

**So I replaced the reranker.** First-place hits went from 105 to 131 out
of 233 — 45% to 56%, p = 0.0001. The honest cost: 16–25 seconds per fresh
question on my laptop. That is a real problem and I have not solved it yet.

**And one that went the other way.**

I was convinced a particular change would help. I ran it. It lost real
ground — p = 0.0215. I rolled it back the same day and wrote it into the
log. A project where every experiment succeeds is a project that is not
measuring anything.

**On "p = 0.0352", in plain words:** it is the chance of seeing a swing
this big if the change actually did nothing. Small means the result is
probably real. It is not proof, and I do not treat it as proof.

Full write-up coming. Happy to talk to anyone doing retrieval on
low-resource languages — there is not much of a map out there.

`#MachineLearning #RAG #InformationRetrieval #Evaluation #NLP #IndicNLP
#Tamil`

---

# The video (post 1)

40–60 seconds. **No voiceover.** LinkedIn autoplays muted, so it must read
in silence. One or two on-screen captions maximum.

| # | shot | seconds |
|---|---|---|
| 1 | empty search box, type the question at human speed | 0–6 |
| 2 | **the thinking screen, in full** — all six stages | 6–30 |
| 3 | scroll 2–3 verse cards: Tamil, transliteration, English, commentary | 30–42 |
| 4 | the written answer; click one citation, jump to that verse | 42–52 |
| 5 | still frame: `78% in the top 5 · 56% at rank 1` | 52–58 |

Shot 2 is the strongest asset in the project and it already exists
(`components/ThinkingScreen.tsx` — six real stages, each drawing its own
mechanism). Do not trim it.

**Which question to film — both were run and checked on 2026-08-10**

### ✅ FILM THIS: *"Should a leader rule through fear?"*

Top score **0.804**. Answer cites 563 and 562. Both checked against the
verse text, both hold:

| cited | what the verse actually says | does the claim hold? |
|---|---|---|
| **563** | "The cruel-sceptred king, who acts so as to put his subjects in fear, will certainly and quickly come to ruin" | **yes** — almost word for word |
| **562** | "Let the king, who desires that his prosperity may long remain, commence his preliminary enquiries with strictness, and then punish with mildness" | **yes** — including "so their rule lasts" |

**One change to the shot list:** scroll **only the top two verse cards**,
not three. Verses 3–5 that day were 680 (Modes of Action), 501 (Selection
of ministers) and 761 (Excellence of an Army) — none of them about ruling
through fear, and their scores were 0.10, 0.015 and 0.008. The answer was
right to ignore them. Do not put them on camera.

### ❌ DO NOT FILM: *"I open my laptop and end up doing nothing for hours"*

**The answer is excellent. The screen is not.**

It found chapter 61, *Unsluggishness*, and cited four verses — 605, 604,
672, 603 — and **all four hold**, checked one at a time. 605 literally
lists procrastination, forgetfulness, idleness and sleep as the vessel of
those destined for ruin. It is the better story, and it worked.

**But every score on screen reads 0.001, 0.000, 0.000, 0.000.**

The reranker's score is a raw relevance number and it is **not calibrated**
(`PROJECT_UNIVERSE.md` §5.7 — `calibrated: false`). A perfectly correct
answer can display as near-zero. On camera, with no voiceover to explain
it, a viewer sees four zeros and concludes the system failed.

This is the exact reason the pre-flight check exists. Keep the question —
it is a great story for the **text** of post 1, where you are describing
what the system does. Just do not put those numbers on screen.

**If you want that question on video**, the honest fix is to calibrate the
score display first (roadmap item 6), not to hide the number.

---

# Who to tag

Only these three. Irrelevant tags reduce reach, and LinkedIn users notice
tag-spam immediately.

| tag | why it is genuine |
|---|---|
| **Sarvam AI** (company page) | their model does the rewriting and writes the answer; ~₹0.005 per query is a real number they would like quoted |
| **AI4Bharat** (IIT Madras) | Indic-language NLP research; Tamil retrieval is exactly their subject |
| **Project Madurai** | they put the text in the public domain; crediting them is correct, and Tamil readers notice who gets credited |

Company page on post 1. Do not tag individual founders on a first post. If
the post does well, mentioning a person in a *reply* is fair.

---

# Timing

Tuesday–Thursday, **9:00–10:30 AM IST**. Post 2 the following week, same
slot. Reply to every comment in the first two hours — that window decides
how far LinkedIn carries the post.

---

# Elsewhere (same video, adapted caption)

| place | why | watch out |
|---|---|---|
| **KaniTamil / Tamil computing conference** | the Tamil-computing crowd; `thirukural.ai` launched there | a 10-minute talk beats any post for your job goal |
| Kaniyam / Tamil FOSS community | the Tamil open-source group; exactly their subject | they will ask "where can I try it" — have the answer ready |
| r/TamilNadu, r/india | large Tamil-reading audience | reddit punishes self-promotion; post as "I built this", reply to everyone |
| r/LanguageTechnology, r/Rag | the evaluation angle lands here | post 2's content, not post 1's |
| X / Twitter | Sarvam's team and the Indic-NLP people are more active here than on LinkedIn | thread version of post 1 |
| ChennaiPy, FOSS United Chennai | local meetups | again: a talk beats a post |
| YouTube Shorts | gives the video a permanent home | lets you link to it later |

---

# Hard rules

1. Every number must appear in `PROJECT_UNIVERSE.md` §12.1.
2. **Never quote 78% without 56% beside it.** §12.1 requires both.
3. Nothing from §12.2 may appear in any wording — not "Sarvam beat the
   local model", not "removing the poem helped", not "Tamil input suits the
   reranker better". None of those are established.
4. Nothing from §12.3 (the leaked rows: 97 / 94 / 89) may be quoted at all.
5. Do not claim the app is live, hosted, or open-source. It is none of
   these today.
6. Do not claim it is the first or only Thirukkural AI. It is not.

---

# Pre-flight checklist

- [x] `./run.sh`, open `http://localhost:3000`, run the chosen question.
      **Done 2026-08-10.** Engine confirmed live as
      `Sarvam HyDE + LaBSE + BM25 + bge-reranker-v2-m3`.
- [x] **Read every cited verse and confirm the sentence above it is really
      supported by that verse.** **Done — passed.** All 2 citations on the
      leader question hold; all 4 on the laptop question hold. See the two
      boxes above for the verse-by-verse check.
- [ ] All six thinking-screen stages visible at recording speed.
- [ ] Record; watch it back **with the sound off**.
- [ ] Check every number in both drafts against §12.1, one at a time.
- [ ] Confirm no draft claims the app is live, hosted, or open-source.
- [ ] Confirm no draft claims it is the first Thirukkural AI.

## The warning

**Tamil readers know these verses.** If the video shows an answer citing a
verse that is not about the question, someone will say so publicly.

This is not hypothetical. An answer to *"how to control anger"*, reviewed
on 2026-08-09, cited kural 343 (chapter 35, renunciation) and kural 471
(chapter 48, judging strength before war). Both are real verse numbers.
Both passed the automatic citation check. Neither is about anger.

The check confirms a number was among the verses supplied. It cannot
confirm the claim is supported by that verse. The measurement that would
catch this — Phase 7's breaking tests — is still open
(`PROJECT_UNIVERSE.md` §11, item 1).

So: verify the filmed question by hand. If any citation does not hold, pick
another question. Do not film and fix afterwards.
