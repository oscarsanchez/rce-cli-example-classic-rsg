# Coding standards

Read during review. `scripts/check` enforces the mechanical rules (both builds, BrighterScript diagnostics, the workflow lint, the pipeline test); these are the judgement calls, each with its reason.

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

`scripts/test_pipeline.py` checks the mechanical rules of `roku-test.yml` and `roku-test-pool.yml`, each test with its reason: every action pinned to a commit SHA with its version tag in a comment; `shell: bash`; `RCE_TOKEN`, `RCE_DEV_PASSWORD` and `RCE_DEV_PASSWORDS` only in the `env` of the steps that need them; the claimed member's Dev Password masked first and passed to the test step alone as a step output, never through `$GITHUB_ENV`; the stop's guard, and its `--run`. It also runs the README's two secret snippets with a fake `rce` and `gh`. What it can't decide:

- A step gets a secret only if it calls `rce`, or, for `RCE_DEV_PASSWORDS`, takes the claimed member's Dev Password out of it. Adding a step to the test's list of a secret's steps is a review decision, not the fix for a red test.
  A step that holds a secret runs code that can read it; `npm ci` alone runs every dependency's install scripts.
- A new SHA pin is the commit its version tag names.
  The test checks the pin's shape, not which commit the tag pointed to.
- No step prints a value taken out of a secret, not only the password step the test runs.
  GitHub masks a secret's whole value, not a part of it.
- A README line that sets a secret goes in one of the two snippets the test runs (the first `sh` block of "Set it up for your own Cloud Device" and of "Parallel jobs on a Pool"), or the test gains a case for it.
  An untested line is how a Dev Password with a trailing newline shipped.

## Vocabulary

- Use the terms in `rce-cli`'s [GLOSSARY.md](https://github.com/oscarsanchez/rce-cli/blob/main/GLOSSARY.md) in code, output and docs: Cloud Device, Run, Device Name, Dev Snapshot, Dev Password. A pass of the suite is a "test run".
  One word per thing lets a reader map this sample onto `rce`'s docs and output.
