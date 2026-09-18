# Roadmap

Where this project goes next, and why.

The system side is in reasonable shape: ingestion, ledger/cache separation, a
persisted model registry with a train/serve split, explainability, tests and CI.
The *experimental* side is thin — nearly every number in the README comes from a
single run on a single dataset, which is weaker evidence than the numbers imply.

The next phase is about measurement, not features. Items are ordered by
dependency: each one needs the one above it.

---

## 1. Deterministic data generation

**Problem.** The generator calls package-level `math/rand`, which Go seeds
randomly. Seeding is one-shot now, so results are stable across restarts — but
every `docker-compose down -v` still produces a different dataset, and so does
every clone of this repo.

**Do.** Take a seed from an env var (`SEED`), construct one `*rand.Rand`, and
thread it through `internal/generator` instead of calling the global functions.

**Why first.** Nothing below is a controlled experiment until the input is
fixed. Someone cloning this should reproduce the README's numbers exactly, not
approximately.

**Size:** small.

---

## 2. Report distributions, not point estimates

**Problem.** Every figure in the README is one draw from one dataset. Reporting
precision as `0.753` claims a precision this experiment cannot support — change
the seed and the third digit is meaningless.

**Do.** Evaluate across N seeds (20 is plenty at this scale) and report
mean ± standard deviation. Update the performance tables to match.

**Why.** It is the difference between "the number I got" and "the number this
method produces." It also shows which of the current results are stable
(Isolation Forest's precision, which is fixed by arithmetic) and which are not
(LOF's, which moves with the data).

**Size:** small, once (1) exists.

---

## 3. Quantify the contamination ceiling — then try to remove it

This is the main piece of work, and the most interesting question the project
has produced.

**Problem.** `contamination` is hardcoded at 0.05 while the true labeled rate is
3.8%, so the detector is required to flag more events than exist. Every false
positive it reports is forced by that gap rather than by a ranking error, and
precision cannot exceed 0.753 while the parameter is wrong. See
[Known limitations](README.md#known-limitations).

**Do, in two parts:**

1. **Measure it.** Sweep `contamination` from 0.01 to 0.15 and plot
   precision/recall/F1 against it. Expect precision to peak where the assumed
   rate meets the true rate, and recall to collapse below it. This turns a
   one-line observation into a curve.
2. **Attack it.** Implement one method that derives the cut from the score
   distribution rather than accepting it as input, and test whether it recovers
   something near 3.8% without being told. A simple knee/threshold heuristic on
   the score distribution is enough to start;
   [Ghosh et al. (2024)](https://arxiv.org/abs/2411.08867) is the direction to
   read for a principled version.

**Honest framing.** The true rate is knowable here *only* because the data is
labeled. On unlabeled production data it is not, which is exactly why this is an
open research problem and not a configuration bug. Part 2 may not beat the
hardcoded value — that is a valid result and should be reported as one.

**Size:** the real work. Several sittings.

---

## 4. Write up the results

**Do.** A short report (4–6 pages, PDF in the repo): problem, method,
experiments, results, limitations, references.

**Why.** The README explains what the system *is*. A report explains what the
experiments *showed* — including where they failed to show anything. These are
different documents and the second one does not exist yet.

**Size:** about a week, after (3).

---

## Optional: does LOF systematically miss clustered anomalies?

On the current dataset LOF's only two misses were both replays — exact
duplicates, which sit in dense neighbourhoods where a local-density score is
least likely to flag them. Two misses cannot settle that.

Sweep replay volume and LOF's `n_neighbors` and find out. Small, self-contained,
and a genuine question rather than a chore.

---

## Deliberately not doing

- **More endpoints, orchestration, or a frontend.** The system already
  demonstrates what it needs to. Additional surface area adds maintenance, not
  evidence.
- **A second project.** Depth on one question is worth more than breadth across
  several.
- **Chasing a better F1.** While `contamination` is guessed, a higher score
  would mostly mean a luckier guess. Understanding the bound is the more
  honest goal than moving it.
