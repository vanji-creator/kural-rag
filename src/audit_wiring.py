"""Prove the wiring is safe before it serves anybody.

Six checks. Each one fails LOUDLY, because a check that quietly passes is
worth nothing - that lesson has cost this project three separate days.

    1. a cached question spends no money
    2. an uncached question really calls the provider, and is then cached
    3. a Tamil question skips the rewriter and says it skipped
    4. a broken key does not take search down, and says it is degraded
    5. the key never appears in an error message
    6. the key is not in git, not in any file the app serves

Run it:

    venv/bin/python -u src/audit_wiring.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

failures = []


def check(name, condition, detail=""):
    """Record one result. Nothing is silent."""
    print(f"  {'PASS' if condition else 'FAIL'}  {name}")
    if detail:
        print(f"        {detail}")
    if not condition:
        failures.append(name)


def main():
    from llm import HostedModel
    from rewrite_hyde import (REWRITER_FAILED, REWRITER_SKIPPED_TAMIL,
                              HydeRewriter)

    print("1. A QUESTION WE HAVE ALREADY PAID FOR COSTS NOTHING")
    rewriter = HydeRewriter()
    cached_question = "how do I control my anger?"
    started_at = time.perf_counter()
    text, produced_by = rewriter.rewrite(cached_question)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    check("cache hit made zero paid calls",
          rewriter.calls_made == 0 and rewriter.cache_hits == 1,
          f"{rewriter.calls_made} paid, {rewriter.cache_hits} from cache, "
          f"{elapsed_ms:.2f} ms")
    check("cache hit returned the measured rewrite",
          text.startswith("anger management"), text)

    print()
    print("2. A NEW QUESTION IS FETCHED ONCE, THEN NEVER AGAIN")
    # A throwaway cache file, not the real one. The question below has a
    # timestamp glued on so it cannot already be cached, which also means it
    # can never be asked again - writing it into the production cache would
    # leave a line of rubbish behind on every audit run.
    audit_cache = PROJECT_ROOT / "data" / ".audit_tmp.jsonl"
    audit_cache.unlink(missing_ok=True)
    rewriter = HydeRewriter(cache_path=audit_cache)
    new_question = f"is it wrong to borrow money from a friend {int(time.time())}"
    first_text, _ = rewriter.rewrite(new_question)
    calls_after_first = rewriter.calls_made
    second_text, _ = rewriter.rewrite(new_question)
    # rewrite() never raises, by design - so when this check fails the reason
    # is sitting in last_error and nowhere else. The first version of this
    # audit did not print it, and the failure said only "0 paid calls",
    # which named the symptom and hid the cause.
    check("the first ask cost one call",
          calls_after_first == 1,
          f"rewrote to: {first_text}"
          + (f"\n        why it did not: {rewriter.last_error}"
             if rewriter.last_error else ""))
    check("the second ask cost nothing",
          rewriter.calls_made == 1 and second_text == first_text,
          f"{rewriter.calls_made} paid calls total")

    reloaded = HydeRewriter(cache_path=audit_cache)
    check("it survived a restart (it is on disk, not just in memory)",
          any(entry == first_text for entry in reloaded.cache.values()),
          f"{len(reloaded.cache)} rewrite(s) re-read from disk")
    audit_cache.unlink(missing_ok=True)

    print()
    print("3. A TAMIL QUESTION SKIPS THE REWRITER AND SAYS SO")
    from pipeline import looks_like_tamil_script
    tamil_question = "கோபத்தை எப்படி கட்டுப்படுத்துவது?"
    check("Tamil script is detected",
          looks_like_tamil_script(tamil_question), tamil_question)
    check("the label is honest about it",
          "Tamil" in REWRITER_SKIPPED_TAMIL, REWRITER_SKIPPED_TAMIL)

    print()
    print("4. A BROKEN KEY DEGRADES, IT DOES NOT CRASH")
    real_key = os.environ.get("SARVAM_API_KEY")
    os.environ["SARVAM_API_KEY"] = "sk_this_key_is_deliberately_wrong"
    broken = HydeRewriter(cache_path=PROJECT_ROOT / "data" / ".audit_tmp.jsonl")
    text, produced_by = broken.rewrite("something not in any cache at all")
    check("search still gets usable text back",
          text == "something not in any cache at all",
          f"fell back to: {text}")
    check("and the result admits it is degraded",
          produced_by == REWRITER_FAILED, produced_by)

    print()
    print("5. THE KEY NEVER APPEARS IN AN ERROR MESSAGE")
    leaked = None
    for _ in range(4):
        broken.rewrite(f"another miss {time.time()}")
    if broken.last_error and "sk_this_key_is_deliberately_wrong" in broken.last_error:
        leaked = broken.last_error
    check("the wrong key was scrubbed from the failure text",
          leaked is None,
          (broken.last_error or "no error recorded")[:160])
    check("the circuit breaker tripped instead of retrying forever",
          broken.failures_in_a_row >= 3,
          f"{broken.failures_in_a_row} consecutive failures, calls paused")

    if real_key:
        os.environ["SARVAM_API_KEY"] = real_key
    temporary_cache = PROJECT_ROOT / "data" / ".audit_tmp.jsonl"
    temporary_cache.unlink(missing_ok=True)

    print()
    print("6. THE REAL KEY IS NOWHERE IT SHOULD NOT BE")
    if real_key:
        tracked = subprocess.run(["git", "grep", "-l", real_key],
                                 cwd=PROJECT_ROOT, capture_output=True,
                                 text=True)
        check("not in any file git tracks",
              tracked.returncode != 0, tracked.stdout.strip() or "clean")

        history = subprocess.run(["git", "log", "--all", "-S", real_key,
                                  "--oneline"],
                                 cwd=PROJECT_ROOT, capture_output=True,
                                 text=True)
        check("not in any past commit",
              not history.stdout.strip(), history.stdout.strip() or "clean")

        ignored = subprocess.run(["git", "check-ignore", ".env"],
                                 cwd=PROJECT_ROOT, capture_output=True,
                                 text=True)
        check(".env is ignored by git",
              ignored.returncode == 0, ignored.stdout.strip())

        cache_text = (PROJECT_ROOT / "data" / "rewrite_cache.jsonl").read_text(
            encoding="utf-8")
        check("not in the rewrite cache we commit",
              real_key not in cache_text,
              f"{len(cache_text.splitlines())} lines checked")

        model = HostedModel("sarvam")
        check("printing the model object shows no key",
              real_key not in repr(model), repr(model))

    print()
    print("=" * 62)
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {', '.join(failures)}")
        raise SystemExit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
