#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8,<9"]
# ///
"""Unit and UI tests for the sample app on a Cloud Device, driven only through `rce --json`.

    RCE_DEVICE=<Device Name or RCE id> uv run tests/test_app.py

Needs a Run already going on that Cloud Device, `build/tests.zip` (the Rooibos test
build, `npm run build:tests`) and `build/app.zip` (`./build.sh`); it starts and stops
no Run. The first test sideloads the test build and reads Rooibos's result line; the
UI tests then sideload the app build. Pass or fail comes from console lines (Rooibos's
report, and the app's lines in README "Console log lines") and ECP answers; each test
saves a screenshot as evidence only. Writes test-results/junit.xml (both kinds),
test-results/console.log and test-results/screenshots/.
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "test-results"
APP_ZIP = ROOT / "build" / "app.zip"
UNIT_ZIP = ROOT / "build" / "tests.zip"

RCE_TIMEOUT = 300  # seconds for one rce call (a sideload waits for the install)
LINE_TIMEOUT = 30  # seconds for the app's next console line after a launch or key
PLAY_TIMEOUT = 60  # seconds from Play to the playing line
ECP_TIMEOUT = 15  # seconds for ECP to agree with the console
UNIT_TIMEOUT = 120  # seconds from the test build starting to Rooibos's result line
CRASH_MARKERS = ("runtime error", "brightscript micro debugger")


class RceError(Exception):
    pass


def rce(*args: str) -> dict:
    """Run `rce <args> --json` and return its JSON; raise RceError on a non-zero exit."""
    command = ["rce", *args, "--json"]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=RCE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RceError(f"`{' '.join(command)}` took over {RCE_TIMEOUT} s")
    if done.returncode != 0:
        raise RceError(f"`{' '.join(command)}` exited {done.returncode}: {done.stderr.strip()}")
    return json.loads(done.stdout)


def ecp_xml(device: str, path: str) -> ElementTree.Element:
    return ElementTree.fromstring(rce("ecp", device, path)["body"])


def wait_for_ecp(read, want, what: str) -> None:
    """Poll `read()` until it returns `want`; fail after ECP_TIMEOUT s with its last answer."""
    deadline = time.monotonic() + ECP_TIMEOUT
    while (answer := read()) != want:
        if time.monotonic() > deadline:
            pytest.fail(f"expected {what} to be {want!r} within {ECP_TIMEOUT:g} s, last answer {answer!r}")
        time.sleep(1)


def fresh_tag() -> str:
    """A tag no earlier run used, so a line the console replays can't match."""
    return "t" + uuid.uuid4().hex[:8]


class Console:
    """The one `rce console` stream of the test run. Every line is kept, in order, so a
    wait that starts after a key press still sees a line printed before it started."""

    def __init__(self, device: str, log: Path):
        self.process = subprocess.Popen(
            ["rce", "console", device, "--strip-ansi", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.lines: list[str] = []
        self.ended = ""  # why the stream ended, once it has
        self.changed = threading.Condition()
        threading.Thread(target=self._read, args=(log,), daemon=True).start()

    def _read(self, log: Path) -> None:
        with log.open("w") as file:
            for output in self.process.stdout:
                line = json.loads(output)["line"]
                file.write(line + "\n")
                file.flush()
                with self.changed:
                    self.lines.append(line)
                    self.changed.notify_all()
        reason = self.process.stderr.read().strip() or f"rce console exited {self.process.wait()}"
        with self.changed:
            self.ended = reason
            self.changed.notify_all()

    def mark(self) -> int:
        """The index the next line will have."""
        with self.changed:
            return len(self.lines)

    def next_line(self, start: int, wanted, timeout: float) -> tuple[int, str]:
        """The first line at or after index `start` for which `wanted(line)` is true, and
        its index. Fails on timeout, on a BrightScript crash line, or if the stream ends."""
        deadline = time.monotonic() + timeout
        index = start
        with self.changed:
            while True:
                for index in range(index, len(self.lines)):
                    line = self.lines[index]
                    if any(marker in line.lower() for marker in CRASH_MARKERS):
                        pytest.fail(f"the app crashed: {line!r}\n{self.tail()}")
                    if wanted(line):
                        return index, line
                index = len(self.lines)
                if self.ended:
                    pytest.fail(f"the console stream ended: {self.ended}\n{self.tail()}")
                left = deadline - time.monotonic()
                if left <= 0:
                    return -1, ""
                self.changed.wait(left)

    def tail(self) -> str:
        return "last console lines:\n" + "\n".join(f"  {line}" for line in self.lines[-15:])

    def close(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=10)


class App:
    """The dev app, launched with a test tag of its own so no earlier line can match.
    `expect` checks the app's next tagged console line, in order."""

    def __init__(self, device: str, console: Console):
        self.device = device
        self.console = console
        self.tag = fresh_tag()
        self.cursor = 0

    def line(self, event: str, fields: str = "") -> str:
        """A console line as the README's "Console log lines" defines it."""
        return " ".join(filter(None, ["sample:", event, f"test={self.tag}", fields]))

    def next_line(self, timeout: float) -> str:
        tagged = f" test={self.tag}"
        index, line = self.console.next_line(
            self.cursor, lambda text: text.startswith("sample: ") and tagged in text, timeout
        )
        if index < 0:
            pytest.fail(f"no console line from the app in {timeout:g} s\n{self.console.tail()}")
        self.cursor = index + 1
        return line

    def expect(self, event: str, fields: str = "", timeout: float = LINE_TIMEOUT) -> None:
        want = self.line(event, fields)
        got = self.next_line(timeout)
        assert got == want, f"expected the console line {want!r}, got {got!r}"

    def expect_playing(self, item: str) -> None:
        """The buffering line, then the playing line (README "Console log lines")."""
        self.expect("playback", f"state=buffering item={item}", PLAY_TIMEOUT)
        self.expect("playback", f"state=playing item={item}", PLAY_TIMEOUT)

    def launch(self) -> None:
        """Launch (or restart) the app with this tag; return once it is ready on the grid."""
        self.cursor = self.console.mark()
        rce("launch", self.device, "--param", f"test={self.tag}")
        self.expect("open", "screen=home item=feat-01")
        self.expect("focus", "screen=home row=0 col=0 item=feat-01")
        self.expect("ready")

    def press(self, key: str) -> None:
        rce("key", self.device, key)


@pytest.fixture(scope="session")
def device() -> str:
    name = os.environ.get("RCE_DEVICE")
    if not name:
        pytest.exit("set RCE_DEVICE to the Cloud Device's Device Name or RCE id", returncode=2)
    for build, command in ((UNIT_ZIP, "npm run build:tests"), (APP_ZIP, "./build.sh")):
        if not build.exists():
            pytest.exit(f"{build.relative_to(ROOT)} is missing: run {command} first", returncode=2)
    status = rce("device", "status", name)
    if status["run"] is None:
        pytest.exit(
            f"no Run is going on {name}: start one with `rce device start {name}`; "
            "the tests start and stop none",
            returncode=2,
        )
    return name


@pytest.fixture(scope="session")
def console(device: str):
    """Opened before anything launches, kept for the whole test run."""
    (RESULTS / "screenshots").mkdir(parents=True, exist_ok=True)
    stream = Console(device, RESULTS / "console.log")
    yield stream
    stream.close()


@pytest.fixture(scope="session")
def installed(device: str, console: Console) -> None:
    """The app build sideloaded once, after the console is open. A test that needs
    another build (the unit tests' build) sideloads it itself and goes before the UI tests."""
    rce("sideload", device, str(APP_ZIP))


@pytest.fixture
def app(device: str, console: Console, installed: None) -> App:
    return App(device, console)


@pytest.fixture(autouse=True)
def screenshot(request: pytest.FixtureRequest, device: str):
    """Evidence after each test, pass or fail; a missing screenshot fails nothing."""
    yield
    path = RESULTS / "screenshots" / f"{request.node.name}.jpg"
    try:
        rce("screenshot", device, "-o", str(path))
    except RceError as error:
        warnings.warn(f"no screenshot for {request.node.name}: {error}")


def tagged_build(build: Path, tag: str) -> tuple[Path, str]:
    """A copy of `build` whose manifest title ends in `tag`, and that title. The device
    prints the title when the app starts, so the copy's output can't be confused with
    an earlier run's that the console replays."""
    copy = RESULTS / f"{build.stem}-{tag}.zip"
    with zipfile.ZipFile(build) as source, zipfile.ZipFile(copy, "w", zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            data = source.read(entry)
            if entry.filename == "manifest":
                lines = data.decode().splitlines()
                title = next(line for line in lines if line.startswith("title=")).removeprefix("title=")
                title = f"{title} {tag}"
                data = "\n".join(f"title={title}" if line.startswith("title=") else line for line in lines)
                data = (data + "\n").encode()
            target.writestr(entry, data)
    return copy, title


ROOIBOS_RESULT = "[Rooibos Result]: "
ROOIBOS_GROUP = re.compile(r"^\s*\|-(?!-)(?P<group>.+?)\s*$")
ROOIBOS_TEST = re.compile(r"\|--(?P<test>.+?) : \.*(?P<status>PASS|FAIL|CRASH|SKIP)\b")


def rooibos_failures(report: list[str]) -> list[str]:
    """Each failed test in Rooibos's console report, as `<describe group>: <test> (FAIL)`
    (or CRASH), then the report's `|--` lines about it: where it is and why it failed."""
    failures, group, failing = [], "", False
    for line in report:
        if match := ROOIBOS_GROUP.match(line):
            group, failing = match["group"], False
        elif match := ROOIBOS_TEST.search(line):
            failing = match["status"] in ("FAIL", "CRASH")
            if failing:
                failures.append(f"{group}: {match['test']} ({match['status']})")
        elif failing and "|--" in line:
            failures.append("    " + line.split("|--", 1)[1].strip())
    return failures


def test_unit_tests_pass(device: str, console: Console):
    """The Rooibos suites (tests/unit) on the device: sideloading the test build starts
    it, and Rooibos prints its report, then `[Rooibos Result]: PASS` or `FAIL`."""
    build, title = tagged_build(UNIT_ZIP, fresh_tag())
    start = console.mark()
    rce("sideload", device, str(build))
    begun, _ = console.next_line(start, lambda line: f"'{title}'" in line, LINE_TIMEOUT)
    if begun < 0:
        pytest.fail(f"the test build '{title}' did not start in {LINE_TIMEOUT} s\n{console.tail()}")
    end, result = console.next_line(begun, lambda line: line.strip().startswith(ROOIBOS_RESULT), UNIT_TIMEOUT)
    if end < 0:
        pytest.fail(f"no Rooibos result line in {UNIT_TIMEOUT} s\n{console.tail()}")
    if result.strip() != ROOIBOS_RESULT + "PASS":
        failures = "\n".join(f"  {line}" for line in rooibos_failures(console.lines[begun:end]))
        pytest.fail(f"Rooibos: {result.strip()}\n{failures or console.tail()}")


def active_app(device: str) -> dict:
    return rce("ecp", device, "query/active-app")["app"]


def media_player_state(device: str) -> str:
    return ecp_xml(device, "query/media-player").get("state", "")


# The query/app-ui readers below answer a value to compare, or a string saying why there
# is none yet (a node missing or not focused mid-transition), so wait_for_ecp asks again.
# An attribute at its default value is left out: a missing `focused` means false, a
# missing `visible` means true.


def grid_focus(device: str):
    """(row, col, tile title) of the grid's focus from ECP query/app-ui, or why there is none.

    The RowList named "grid" has focused="true" only while it holds real focus, and its
    focusItem is the row. Every row's MarkupGrid flags a tile of its own, so the column
    and title come from the one row node in the focus chain (focused="true")."""
    grid = ecp_xml(device, "query/app-ui").find(".//RowList[@name='grid']")
    if grid is None or grid.get("focused") != "true":
        return "the grid does not have focus"
    rows = [row for row in grid.findall("RowListItem") if row.get("focused") == "true"]
    if len(rows) != 1:
        return f"{len(rows)} grid rows claim focus"
    tiles = rows[0].find("MarkupGrid")
    if tiles is None:
        return "the focused grid row has no tiles yet"
    focused = [tile for tile in tiles.findall("GridItem") if tile.get("focused") == "true"]
    if len(focused) != 1:
        return f"{len(focused)} tiles in the focused row claim focus"
    title = focused[0].find("Label[@name='title']")
    if title is None:
        return "the focused tile has no title yet"
    return int(grid.get("focusItem")), int(tiles.get("focusItem")), title.get("text")


def wait_for_grid_focus(device: str, want: tuple[int, int, str]) -> None:
    wait_for_ecp(lambda: grid_focus(device), want, "query/app-ui grid focus")


def shown_screen(device: str, node: str, name: str):
    """The screen node `node` named `name` from query/app-ui if it is visible and in the
    focus chain, or why not."""
    screen = ecp_xml(device, "query/app-ui").find(f".//{node}[@name='{name}']")
    if screen is None:
        return f"no {node} named {name!r}"
    if screen.get("visible") == "false":
        return f"the {name} screen is hidden"
    if screen.get("focused") != "true":
        return f"the {name} screen does not have focus"
    return screen


def details_title(device: str):
    """The title the details screen shows, from query/app-ui, if that screen is visible and
    has focus; or why there is none."""
    screen = shown_screen(device, "DetailsScreen", "details")
    if isinstance(screen, str):
        return screen
    title = screen.find(".//Label[@name='title']")
    return "the details screen has no title yet" if title is None else title.get("text")


def player_shown(device: str):
    """`shown` while the player screen is visible and has focus, from query/app-ui; or why not."""
    screen = shown_screen(device, "Video", "player")
    return screen if isinstance(screen, str) else "shown"


def test_ready(app: App, device: str):
    app.launch()
    front = active_app(device)
    assert front.get("id") == "dev", f"expected the dev app in front, ECP query/active-app says {front}"


def test_focus_moves_right_and_down(app: App, device: str):
    app.launch()
    wait_for_grid_focus(device, (0, 0, "Morning Signal"))
    app.press("Right")
    app.expect("focus", "screen=home row=0 col=1 item=feat-02")
    wait_for_grid_focus(device, (0, 1, "Paper Harbour"))
    app.press("Down")
    app.expect("focus", "screen=home row=1 col=1 item=nat-02")
    wait_for_grid_focus(device, (1, 1, "Tide Tables"))


def test_select_opens_details_for_the_focused_item(app: App, device: str):
    app.launch()
    app.press("Right")
    app.expect("focus", "screen=home row=0 col=1 item=feat-02")
    app.press("Select")
    app.expect("open", "screen=details item=feat-02")
    wait_for_ecp(lambda: details_title(device), "Paper Harbour", "query/app-ui details title")


def test_play_reaches_playing(app: App, device: str):
    app.launch()
    app.press("Select")
    app.expect("open", "screen=details item=feat-01")
    app.press("Select")
    app.expect("open", "screen=player item=feat-01")
    app.expect_playing("feat-01")
    wait_for_ecp(lambda: player_shown(device), "shown", "query/app-ui player screen")
    wait_for_ecp(lambda: media_player_state(device), "play", "ECP query/media-player state")


def test_back_returns_to_the_grid_with_the_same_item_focused(app: App, device: str):
    app.launch()
    app.press("Right")
    app.expect("focus", "screen=home row=0 col=1 item=feat-02")
    app.press("Down")
    app.expect("focus", "screen=home row=1 col=1 item=nat-02")
    app.press("Select")
    app.expect("open", "screen=details item=nat-02")
    app.press("Select")
    app.expect("open", "screen=player item=nat-02")
    app.expect_playing("nat-02")
    app.press("Back")
    app.expect("playback", "state=stopped item=nat-02")
    app.expect("open", "screen=details item=nat-02")
    app.press("Back")
    app.expect("open", "screen=home item=nat-02")
    app.expect("focus", "screen=home row=1 col=1 item=nat-02")
    wait_for_grid_focus(device, (1, 1, "Tide Tables"))


if __name__ == "__main__":
    sys.exit(
        pytest.main(
            [__file__, "-v", "-p", "no:cacheprovider", f"--junitxml={RESULTS / 'junit.xml'}"]
            + sys.argv[1:]
        )
    )
