# Coding standards

Read during review. `scripts/check` enforces the mechanical rules (both builds, BrighterScript diagnostics, the workflow lint); these are the judgement calls, each with its reason.

## Test oracles

- A test passes on a signal independent of the code under test: `query/app-ui`, another ECP answer, or Rooibos's result line, beside the app's own console line.
  The app's log line alone can say "focused" while the screen disagrees; a second source catches that.
- Screenshots are evidence only: saved for people, never what a test asserts on.
  An image comparison is brittle across Cloud Devices and says nothing about which node has focus.
- Every wait has a timeout and fails on it, with what it last saw in the message.
  An unbounded wait in a billed Run turns a bug into minutes on the bill, and a silent timeout into a false pass.

## The console log-line contract

- The line format is one contract shared by `components/lib/testlog.brs` (builds the text), the README's [Console log lines](README.md#console-log-lines) table (documents it) and `tests/test_app.py` (parses it). A change to it touches all three in the same change.
  Anyone driving the app copies the README, so a drift between the three breaks their tests, not ours.

## README walkthroughs

- Every walkthrough starts a Run before the first step that needs one, and ends with `rce device stop`, `rce device list --running` and what it cost.
  Readers paste the steps in order; a step before the start fails, and a walkthrough without a stop bills until the Run's cap.

## The pipeline

- `roku-test.yml` keeps the guarded start and stop of the `rce-cli` README's Pipelines recipe: the stop runs once the start step ran, on failure and cancel too, skips when RCE refused the start (exit 4), and passes the Run id the start recorded with `--run`.
  Without the guard a failed job leaves a Run billing, or stops someone else's; without `--run` it stops a Run someone else started after this job's Run ended.
- Every action is pinned to a full commit SHA, its version tag in a comment.
  A tag can be moved to other code; a SHA cannot, and these jobs hold the RCE token.
- Secrets go in the `env` of only the steps that call `rce`.
  Every other step (`npm ci`, a build) then runs code that cannot read them.

## Vocabulary

- Use the terms in `rce-cli`'s [GLOSSARY.md](https://github.com/oscarsanchez/rce-cli/blob/main/GLOSSARY.md) in code, output and docs: Cloud Device, Run, Device Name, Dev Snapshot, Dev Password. A pass of the suite is a "test run".
  One word per thing lets a reader map this sample onto `rce`'s docs and output.
