# Outreach — organisations for Kural RAG

Who to write to, why each one genuinely fits, what to send, and the email
drafts. The lead is **Tamil literature made usable by modern engineering**;
the codebase is the proof that follows, not the opening line.

Every organisation below was checked on the web on 2026-08-09. Where I
could not verify something, it says so.

---

## First, three decisions to make before sending anything

**1. What "share the repo" means.** The repo is private. Sharing it means
adding a named person as a collaborator on GitHub — one person, revocable.
That is fine and normal. Do not make it public just to share it with three
people.

**2. Send the document, not the repo, first.** `PROJECT_UNIVERSE.md` is
already the complete reference — pipeline, every experiment, every mistake,
the claims inventory. Export it to PDF and attach that. Offer repo access
in the last line, for whoever asks. Nobody opens a stranger's repo cold;
plenty of people read a good document.

**3. Ask for something small.** Not funding. Not a partnership. Twenty
minutes, or a reaction to the document. A first email that asks for money
gets no reply and burns the contact.

---

## Tier 1 — closest fit, write to these first

### 1. Onemai Foundation — Vignesh Sundaresan (Metakovan)

**Verified:** Singapore-based non-profit working at the intersection of art
and technology, founded by Vignesh Sundaresan. Its Tamil work is real and
recent:

- **Tamil Font Studio** (2024) — a platform for creating and celebrating
  Tamil typefaces, run with the Roja Muthiah Research Library.
- **Anbenum Peruveli** — Vallalar's poetry rebuilt for a modern audience,
  with Sanjay Subrahmanyan and Sean Roldan.
- **Mummai** — a public file registry they develop as shared infrastructure.

**Why this is the best single fit:** their pattern is exactly yours — take
a classical Tamil work and make it live in a modern medium, and build the
technical infrastructure underneath rather than just commissioning art.
Vallalar's poetry set to new music is the same move as the Thirukkural made
searchable in plain English.

**One advantage you should use:** Sundaresan is a software engineer by
background (YCombinator 2014, blockchain infrastructure). He will read a
measured evaluation table properly. Most people you email will not. Do not
soften the engineering for him — lead with it.

**Draft email → below, §"Email A".**

---

### 2. Roja Muthiah Research Library (RMRL), Chennai

**Verified:** founded 1994, Taramani, Chennai. ~500,000 items; more than 3
million page images digitised; over 1,500,000 pages preserved in digital
and microfilm. Contact listed publicly as `rmrl@rmrl.in`, phone 22542551/2.

**Why it fits:** they are the largest private Tamil archive in the world
and their problem is the one you worked on — a vast amount of Tamil text
that nobody can search by meaning. They already collaborate with Onemai, so
a warm introduction is possible if email A goes well.

**The honest ask:** not "look at my project" but "does semantic search over
Tamil text solve anything you actually have?" That is a question they can
answer, and it is genuinely useful to you.

---

### 3. Sarvam AI

**Why:** their model does your query rewriting and writes your final
answer, at roughly ₹0.005 per query. A named Indian developer with real
measured numbers using their model for classical Tamil is a story they
want. Companies rarely get clean case studies from individual developers.

**What to send:** the video, the cost-per-query figure, and the honest
scorecard. Ask nothing except whether they would like to feature it.

**Do not send:** any comparison claiming their model beat another one. Your
own log marks that NOT ESTABLISHED (p = 0.0534). Sending an unsupported
claim to the company that made the model is the worst possible place to be
caught overclaiming.

---

## Tier 2 — Tamil computing and NLP

### 4. AI4Bharat, IIT Madras

Indic-language NLP research group — translation, speech, understanding
across Indian languages, all open-sourced. Chennai-based.

**Why it fits:** retrieval on a low-resource language, with a hand-built
evaluation set and paired significance testing, is close to publishable and
squarely their subject. They are also the most likely group on this list to
tell you your methodology is wrong — which is worth more than praise.

**Ask:** would the golden set be useful to anyone there, and is the
methodology sound?

### 5. Kaniyam Foundation / KaniTamil conference

The Tamil free-software and Tamil-computing community, and the annual
conference. `thirukural.ai` launched at KaniTamil24 and went viral from
there.

**Why it fits:** this is where Tamil-computing work is presented, not just
posted. **A ten-minute talk here is worth more than any LinkedIn post for
your stated goal.** Find the next conference's call for talks and submit.

### 6. Tamil Virtual Academy (Tamil Nadu Government, IT Department)

Runs a long-term programme on Tamil language technology and NLP — spell
checkers, OCR, summarisation, speech, translation — and runs
*kanitamilperavai* in 100 colleges, with 10,000+ registered students.

**Why it fits:** they fund and publicise Tamil language technology, and
they need demonstrations for those 100 colleges. Government pace is slow;
send it, then forget about it.

---

## Tier 3 — Thirukkural and heritage specifically

### 7. Central Institute of Classical Tamil (CICT), Chennai

Government institute. Currently digitising Thirukkural palm-leaf
manuscripts — 640 of 1330 couplets verified so far (48.1%) under its
Digital Archives of Classical Tamil.

**Why it fits:** they are producing the authoritative digital Thirukkural
while you built a way to search one. Direct, obvious overlap.

### 8. International Thirukkural Foundation — 2026 conference

Verified: a 2026 conference in Jaffna, Sri Lanka, themed *"Thirukkural:
Universal Values for Global Harmony"*, with published proceedings, a
special journal issue, and a digital archive of presentations.

**Why it fits — and this is the strongest concrete opportunity on this
page:** a published paper on retrieval evaluation over the Thirukkural
would be a real academic credit, from work you have already done. You have
the numbers, the method, and the negative results. That is a paper.

I could not find the call-for-papers details or deadline. Check
`thirukkuralfoundation.com` directly or write and ask.

### 9. Tamil Heritage Foundation

Founded 2001, digitises Tamil manuscripts and monuments, with volunteers in
India, Malaysia, Sri Lanka, Germany, USA, South Africa, Denmark, France,
Netherlands and the UK.

**Why it fits:** an international volunteer network — the fastest way for
one project to be seen in several countries at once.

### 10. Noolaham Foundation (Sri Lanka)

Tamil digital library, volunteer-run, large Sri Lankan Tamil readership.

### 11. Project Madurai

**Write to them regardless of everything else on this page.** Their
volunteers typed the Thirukkural into the public domain decades ago, and
their text is what your corpus is built from. They should hear about it
from you before they read it in a post. Cost: one short email. This is
courtesy, not strategy.

---

## Tier 4 — the people who built the other one

### 12. Dream Tamilnadu / Suresh Sambandam (thirukural.ai)

They built `thirukural.ai` — GPT-4 with RAG, Tamil/English/Thanglish,
launched at KaniTamil24, reportedly 100,000 users in a day.

**Why write to them at all:** because pretending they do not exist is worse
than approaching them. They solved the same problem at a scale you have not
reached, and you measured a part of it that most demos never touch. Peers,
not rivals.

**The ask:** would they compare notes on retrieval evaluation? That email
is easy to answer and hard to resent. It also protects you — the day
someone puts their link in your comments, you can already say you have been
in touch.

---

## What to attach, in every case

| item | why |
|---|---|
| the 40–60 s demo video | most people will only watch this |
| `PROJECT_UNIVERSE.md` as PDF | for the few who read; it is already complete |
| repo access **on request only** | private repo, one named collaborator at a time |

Do not attach the golden set or the logs. Nothing in this project needs to
leave your machine except the document and the video.

---

## Email A — Onemai Foundation / Vignesh Sundaresan

Subject: **A search engine for the Thirukkural — 1330 verses, measured**

> Hello Vignesh,
>
> I saw the Tamil Font Studio and Anbenum Peruveli — taking a classical
> Tamil work and rebuilding it for a modern medium, with the technical
> infrastructure underneath rather than around it. I have spent the last
> few weeks on a small version of the same idea, and I think you are one of
> the few people who would read the engineering rather than skip it.
>
> **Kural RAG** lets anyone ask a question in plain English, Tamil, or
> Thanglish and get the Thirukkural verses that actually answer it — plus a
> short written answer where every sentence carries the number of the verse
> it rests on.
>
> The interesting problem was not the language model. It was this: a text
> written 2,000 years ago has no word for "laptop", so a question about
> wasting a day on one shares no words with any verse. The system rewrites
> the question into the vocabulary the text itself uses before it searches.
>
> The part I care about more is that I can tell you whether it works. I
> wrote 100 test questions by hand and checked the correct verse numbers
> for each, one at a time. Retrieval went from 44 correct to 97, one
> measured change at a time. On a larger 233-question set, a correct verse
> is in the five shown 78% of the time, and is the first one shown 56% of
> the time. I report the second number because it is the weaker one.
>
> It is not hosted yet — it runs on my laptop, at about half a paisa per
> question.
>
> I am not asking for funding. I would value twenty minutes of your
> reaction, or simply your view on whether this kind of thing is useful to
> the Tamil work Onemai supports. I can send a 60-second video, a full
> technical write-up, or access to the code — whichever you prefer.
>
> Thank you for the work you are funding. There is not much of it.
>
> Vikash (Vanji)
> [phone] · [LinkedIn]

**Why it is shaped this way**

- Opens with his actual projects by name. Anything less specific reads as a
  template and gets deleted.
- The laptop line is the memorable part, and it is true.
- Numbers arrive with the weak one included. To an engineer, volunteering
  your worst number is the strongest credibility signal available.
- The ask is twenty minutes. Not money, not a partnership.
- No attachment on the first email — attachments from strangers do not get
  opened, and a link offered is a reply invited.

---

## Email B — archives and institutions

For RMRL, CICT, Tamil Heritage Foundation, Noolaham, Tamil Virtual Academy.
Same body, different second paragraph.

Subject: **Semantic search over classical Tamil — would this be useful to you?**

> Hello,
>
> I am a software engineer in [city]. I built a system that searches the
> Thirukkural by *meaning* rather than by words: someone asks a question in
> ordinary English or Tamil, and it finds the verses that answer it even
> when the question and the verse share no words at all.
>
> *[RMRL: I understand you have digitised over three million page images.
> That is the reason I am writing — a scanned page is preserved, but it is
> not yet findable by meaning.]*
> *[CICT: I understand you have verified 640 of the 1330 couplets from
> palm-leaf manuscripts. Mine works on the printed text; yours is the
> authoritative source.]*
>
> I am not selling anything. I built it to learn, and I measured it
> properly: 100 hand-written test questions with hand-checked answers, and
> retrieval improved from 44 correct to 97 over several measured changes.
>
> My question is simple: **is searching Tamil text by meaning a problem you
> actually have?** If it is, I would happily show you what I have and hear
> where it falls short. If it is not, that is a useful answer too.
>
> Vikash (Vanji)
> [phone] · [LinkedIn]

---

## Email C — Project Madurai (courtesy)

Subject: **Thank you — your Thirukkural text is running a search engine**

> Hello,
>
> The Thirukkural text your volunteers typed and released is the corpus
> behind a search system I built: it answers questions in English, Tamil
> and Thanglish by finding the verses that actually apply.
>
> I wanted you to hear it from me, and to say that the decision to put that
> text in the public domain decades ago is the only reason a project like
> this was possible for one person with no budget. I credit Project Madurai
> in everything I publish about it.
>
> If you would like to see it, I will send a short video.
>
> Thank you,
> Vikash (Vanji)

---

## Honest expectations

Cold email to a foundation gets a reply maybe one time in five, often
weeks later. That is normal and not a verdict on the work. Send them in one
sitting, keep a note of who and when, follow up **once** after two weeks,
then stop.

The highest-value action on this page is not an email at all. It is
**submitting a talk to KaniTamil or a paper to the Thirukkural conference**
— you already have the results, and both put you in front of the exact
people, with a record that outlasts a post.
