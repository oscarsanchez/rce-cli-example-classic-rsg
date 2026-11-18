# RCE Sample: a classic Roku app on Roku Cloud Emulator

A small, original BrightScript and SceneGraph app (a home grid, a details screen and a video player) that you build with `zip` and run on a Cloud Device with [`rce`](https://github.com/oscarsanchez/rce-cli), a command-line client for Roku® Cloud Emulator (RCE). Copy its everyday loop into your own classic project: nothing here is specific to this app except the file names.

`rce-cli-example-classic-rsg` is a sample app for Roku® Cloud Emulator, not affiliated with or endorsed by Roku, Inc. ROKU is a trademark and/or registered trademark of Roku, Inc. in the United States and other countries.

Licence: [MIT](LICENSE) for the code. The video is not part of this repo; see [Credits](#credits).

## Prerequisites

- macOS or Linux, with `zip` (preinstalled on macOS).
- `rce` installed, an RCE token set, and a Cloud Device set up for development. Follow `rce-cli`'s [Getting started](https://github.com/oscarsanchez/rce-cli#getting-started): it covers the token, creating or naming a Cloud Device, and `rce device setup-dev`, which gives it developer mode, a Dev Password and a Dev Snapshot. The examples below call that Cloud Device `player`; use your own Device Name.

There is no SDK, Node or build tool to install for the app: it is plain BrightScript and SceneGraph XML. The tests need two more things: [Node](https://nodejs.org/) (a current LTS; checked with 22) for the unit tests' build only, and [uv](https://docs.astral.sh/uv/), which fetches Python and pytest for the test run.

## What's in it

```
manifest
source/main.brs              entry point: reads the `test` launch param, shows MainScene
components/MainScene.*       moves between the screens, handles Back, prints the console lines
components/HomeScreen.*      the grid: a RowList of the catalog's rows
components/GridItem.*        one grid tile
components/DetailsScreen.*   title, duration, description and a Play button
components/lib/catalog.brs   ParseCatalog and FormatDuration: plain functions, no nodes
components/lib/testlog.brs   the console lines' text: plain functions, no nodes
data/catalog.json            the bundled catalog: three rows of five items
images/icon_focus_hd.png     the app icon
build.sh                     builds build/app.zip
tests/unit/*.spec.bs         the unit tests: Rooibos suites for components/lib
bsconfig.tests.json          the unit tests' build: BrighterScript and the Rooibos plugin
package.json                 pins brighterscript and rooibos-roku, and runs that build
tests/test_app.py            runs the unit tests, then the UI tests: pytest, run as a uv script
```

The catalog is made up and bundled with the app, so there is no backend. Every item plays the same stream, Big Buck Bunny.

Keys: arrows move on the grid, OK opens details, OK on Play starts the video. Back from the player returns to details, and Back from details returns to the grid with the same tile focused. Back on the grid exits the app.

## Build

```sh
./build.sh            # writes build/app.zip
```

It is one `zip` of `manifest`, `source`, `components`, `data` and `images`. `build/` is not committed.

## The everyday loop

In a second terminal, connect the console before the app starts, and leave it running:

```sh
rce console player --strip-ansi                 # every console line as it arrives; Ctrl-C to quit
```

Then:

```sh
./build.sh
rce device start player --max-runtime 1800      # waits until it takes input (about 80 s); billing starts now
rce sideload player build/app.zip               # installs and starts the app; the console prints "sample: ready"
rce launch player --param test=run1             # restarts it with test logging on: "sample: ready test=run1"
rce key player Right Down Select --delay 1000   # move focus, open details; the console prints focus and open lines
rce screenshot player -o shot.jpg               # the app's screen as a JPEG, video frame included
rce device stop player                          # billing ends here
rce device list --running                       # check nothing is left on
```

A device takes one console client at a time, so in a script, wait for the ready line instead of streaming:

```sh
rce console player --until 'sample: ready test=run2' --timeout 120 &   # connect before launching
rce launch player --param test=run2
wait                                                                    # exits 0 on the ready line, 5 on timeout
```

`rce ecp player query/active-app` confirms the dev app is in front, and `rce ecp player query/app-ui` returns its SceneGraph node tree (RCE serves it). The RCE web console shows the Cloud Device live.

## Console log lines

The app always prints one line when the home grid is on screen and takes keys:

```
sample: ready
```

Launched with the `test` launch param (`rce launch player --param test=<tag>`), it prints the ready line with the tag, and one line for each of these events:

| Event | Line |
|---|---|
| Ready | `sample: ready test=<tag>` |
| A screen opened | `sample: open test=<tag> screen=<screen> item=<item id>` |
| Focus moved on the grid | `sample: focus test=<tag> screen=home row=<row> col=<col> item=<item id>` |
| The video's state changed | `sample: playback test=<tag> state=<state> item=<item id>` |

- Every line starts `sample: `, then the event, then `key=value` fields in the order shown, separated by single spaces. No value contains a space.
- `<tag>` is the value you passed. Use letters, digits, `-` and `_`, and a new one for each launch: the console can replay earlier output when you connect, and a new tag can't match an old line.
- `<screen>` is `home`, `details` or `player`. `<row>` and `<col>` count from 0. `<item id>` is the item's `id` in `data/catalog.json`; on `open screen=home` it is the focused tile.
- `<state>` is the SceneGraph Video node's `state`: `buffering`, `playing`, `paused`, `stopped`, `finished` or `error`.

What you see, in order:

- **Launch:** `open screen=home`, `focus ... row=0 col=0`, then `ready`.
- **Arrow keys on the grid:** one `focus` line per move. A key that doesn't move focus (Left on the first tile) prints nothing.
- **OK on a tile:** `open screen=details` for that tile's item.
- **OK on Play:** `open screen=player`, then `playback state=buffering` and `playback state=playing`.
- **Back from the player:** `playback state=stopped`, then `open screen=details`.
- **Back from details:** `open screen=home`, then `focus` for the tile that was focused before.
- **The video ends or fails:** `playback state=finished` or `state=error`, and the app returns to details.

For example, from launch to Play on the second row's third tile:

```
sample: open test=run1 screen=home item=feat-01
sample: focus test=run1 screen=home row=0 col=0 item=feat-01
sample: ready test=run1
sample: focus test=run1 screen=home row=0 col=1 item=feat-02
sample: focus test=run1 screen=home row=0 col=2 item=feat-03
sample: focus test=run1 screen=home row=1 col=2 item=nat-03
sample: open test=run1 screen=details item=nat-03
sample: open test=run1 screen=player item=nat-03
sample: playback test=run1 state=buffering item=nat-03
sample: playback test=run1 state=playing item=nat-03
```

These lines are the contract between the app and anything that drives it, such as UI tests: change their format and you change those too. The text is built in `components/lib/testlog.brs`. Without the `test` param the app prints only `sample: ready` (or, if the bundled catalog can't be read, a line saying so instead).

## Unit tests

The plain logic in `components/lib` (catalog parsing, `FormatDuration` and the console lines' text) has [Rooibos](https://github.com/rokucommunity/rooibos) unit tests in `tests/unit/`. They are BrighterScript, so they need a build of their own; the app keeps its plain `zip` build and never needs Node.

```sh
npm ci                  # once: brighterscript and rooibos-roku, at the versions package.json pins
npm run build:tests     # writes build/tests.zip
```

`bsconfig.tests.json` compiles `manifest`, `components`, `data` and `images` (the app without `source/main.brs`) and the suites, with the Rooibos plugin, which adds the framework and a `main` that runs the suites instead of the app. The suites run on the main thread, in source scope, but `components/lib` is in component scope, so `npm run build:tests` first copies `components/lib/*.brs` to `build/unit-lib/`, and the build places those copies in `source/lib` as well. The app's own files are unchanged. To test another plain-logic file, put it in `components/lib` and add a suite.

Sideloading the test build starts it, and Rooibos prints a report to the console, ending in its result line:

```
 [START TEST REPORT]
 ...
 Total: 15
   Passed: 15
 ...
 RESULT: Success
 [END TEST REPORT]
[Rooibos Result]: PASS
[Rooibos Shutdown]
```

`[Rooibos Result]: FAIL` means a test failed or crashed. In the report, a failed test's line ends in `FAIL` (or `CRASH`), followed by where the assertion failed and its message. To try it by hand: `rce console player --strip-ansi` in one terminal, `rce sideload player build/tests.zip` in another.

The test run below runs them for you, first.

## UI tests

`tests/test_app.py` drives the app on a Cloud Device and checks its main paths: it reaches ready with the dev app in front, focus moves right and down on the grid, Select opens details for the focused tile, Play reaches playing, and Back (from the player, then from details) returns to the grid with the same tile focused. It is a pytest file run as a uv script, its dependencies inline, and it talks to the device only through `rce ... --json`.

One command runs the unit tests and then the UI tests, against your own Cloud Device:

```sh
./build.sh                                      # build/app.zip
npm run build:tests                             # build/tests.zip (after npm ci, once)
rce device start player --max-runtime 900       # the tests need a Run going; they start and stop none
RCE_DEVICE=player uv run tests/test_app.py      # or ./tests/test_app.py; takes about a minute and a quarter
rce device stop player
rce device list --running
```

The first test, `test_unit_tests_pass`, sideloads the test build, waits for `[Rooibos Result]:` and fails unless it says `PASS`, naming each failed test with the report's lines about it, for example:

```
Failed: Rooibos: [Rooibos Result]: FAIL
  console lines: focus line (FAIL)
    Test : file:///.../tests/unit/testlog.spec.bs:29
    Failed at: file:///.../tests/unit/testlog.spec.bs:30
    Error Message: expected ""sample: focus test=run1 screen=home …" to equal ""sample: focus test=run1 screen=home …"
```

Rooibos shortens long values in its messages (the `…`); the line numbers point at the assertion. The test sideloads a copy of the test build whose manifest title ends in a fresh tag, and reads only the report printed after the device starts that title, so a result replayed from an earlier run can't pass it. The UI tests then sideload the app build.

`RCE_DEVICE` is a Device Name or an RCE id. Other arguments go to pytest, for example `-k unit_tests`, `-k focus` or `-x`. The exit code is pytest's: 0 when every test passed, 1 when one failed, 2 when the suite refused to start (no `RCE_DEVICE`, no `build/tests.zip` or `build/app.zip`, or no Run going). It writes, under `test-results/` (not committed):

- `junit.xml`, one JUnit report for the unit tests (as one test case) and the UI tests;
- `console.log`, every console line the session saw;
- `tests-<tag>.zip`, the tagged copy of the test build it sideloaded;
- `screenshots/<test name>.jpg`, the screen at the end of each test, pass or fail.

While it runs, leave the device alone: close your own `rce console` first (a device takes one console client, and the suite holds it for the whole session) and press no keys.

How a test decides:

- **Console lines first.** The suite opens one console stream before anything launches and keeps every line, so a line printed between a key press and the wait for it is not missed. Each test relaunches the app with a new `test` tag (launching restarts it), so a line replayed from earlier can't match, and checks the app's next tagged lines one by one, in order, against the [Console log lines](#console-log-lines). Every wait has a timeout and fails on it, with the last console lines in the message. A BrightScript crash line (`runtime error`, the Micro Debugger) fails the test at once.
- **ECP as a second signal.** `query/active-app` must name the dev app; on Play, `query/media-player` must reach `state="play"`; and on the grid, `query/app-ui` must agree with the focus line (below).
- **Screenshots are evidence only.** A failed or missing screenshot is a warning; no test passes or fails on one.

`query/app-ui` on RCE: RCE serves it (checked on a Cloud Device in November 2026): the app's SceneGraph tree, about 235 lines for this app. The grid's focus reads from it like this, and the focus tests check it:

- the RowList named `grid` has `focused="true"` only while it holds real focus (on details it is absent), and its `focusItem` is the focused row;
- every row's MarkupGrid flags a tile `focused="true"` of its own, so read the column (its `focusItem`) and the tile's title only from the one row node (`RowListItem`) in the focus chain, the one with `focused="true"`;
- an attribute at its default value is left out, so a missing `focused` means false.

A wrong expectation fails with what was expected and what came instead, for example `expected the console line 'sample: focus test=t8ec16e70 screen=home row=1 col=2 item=nat-03', got '... row=1 col=1 item=nat-02'` or `expected query/app-ui grid focus to be (1, 2, 'Tide Tables') within 15 s, last answer (1, 1, 'Tide Tables')`.

Cost: a Run from start to stop around the suite is about 3 device-minutes, about one cent.

## Costs

A Run costs $0.20 per hour, billed by the minute from the moment `rce device start` asks for it, and RCE has no idle stop: it bills until you stop it or it reaches its cap. `--max-runtime` sets the cap (the default is 3600 s). The RCE trial gives 600 free minutes and allows one Run at a time across the organisation.

The loop above, run start to stop without pauses, takes about 3 device-minutes, about one cent. Every walkthrough ends with `rce device stop` and `rce device list --running`; `rce device status player` shows a Run's elapsed cost and `rce usage` the minutes used. Details: `rce-cli`'s [Costs](https://github.com/oscarsanchez/rce-cli#costs).

## Credits

The video is [Big Buck Bunny](https://peach.blender.org/), (c) copyright 2008, Blender Foundation, www.bigbuckbunny.org, licensed under [Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/). The app streams it from Mux's public test streams (`https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8`, HLS); it is not stored in this repo and the MIT licence does not cover it.

The catalog's titles and descriptions, the icon and the code are original to this repo.
