# FASIM III Style Guide

These instructions define the expected coding and documentation style for
everything in this repository: the simulator `FASIM3.py`, its tests under
`tests/`, and the Markdown that documents them.

FASIM3 is a Python port of FASIMNEW, a Turbo Pascal 5.0 discrete-event
simulation of field artillery fire units and supply units moving over a
network. The goal is clarity, consistency, strong pedagogical value, and a
port whose behavior can be checked line by line against the Pascal source.

---

## General Principles

- Code should be **clear, explicit, and readable**.
- Prefer **teaching-oriented explanations** over compact or clever code.
- Write as if the reader is a **student learning the concept for the first
  time**, or an engineer comparing the port against the Pascal original.
- Avoid unnecessary abstraction unless it improves understanding.
- The Pascal source is the specification. When a Python idiom and the
  original algorithm disagree, keep the original algorithm and say why in a
  comment.

---

## Fidelity to the Pascal Source

The port is only useful if its output can be trusted against FASIMNEW, so
the model code keeps the original's structure even where Python would
normally do it differently.

- Constants, procedure names, record fields, and model variable names follow
  the Pascal source: `Node`, `Conn`, `TravelTime`, `MinTime`, `FU`, `SU`,
  `EventQ`, `RNFSeed`, `Clock`, `DataFile`, `ProcFURQO`, and so on. These
  are `PascalCase` on purpose. Do not rename them to `snake_case`, and do
  not "modernize" them.
- Node and unit numbering starts at 1. Index 0 of any model array is unused.
- `Random(RNFSeed, Typ)` updates the caller's seed through the mutable
  `SeedRec`, as Pascal's `var` parameter does. Never replace it with
  `random` or `numpy.random`; the Park-Miller sequence is part of the
  specification and the tests check it value by value.
- `math.trunc` stands in for Pascal truncation toward zero. Do not swap it
  for `int()` on a negative value, `round()`, or floor division without
  checking the Pascal statement it reproduces.
- The report written to `SimRun.Doc` preserves the Pascal wording, fields,
  ordering, decimal precision, ASCII encoding, and CRLF line endings.
  `tests/fixtures/pascal-default.doc` records the original program's default
  run and is the reference the report is compared against.
- Model conventions that look like bugs are deliberate and documented in
  `README.md`: the first event beyond `MaxClock` is processed, several
  durations are credited when scheduled, and state times are not a strict
  partition of the horizon. Do not "fix" them. If one must change, change
  the fixture in the same commit and explain the difference in the README.

New code that is not part of the model (argument parsing, display helpers,
tests) also uses `PascalCase` for functions and variables so that the file
reads as one style. Ruff's naming rules are not enabled for this reason.

---

## Code Comments

Comments describe the code **as it stands now**, in the present tense. The
reader sees only the current version, so anything about the code's past is
confusing noise.

- **Never refer to a prior version of the code**, an earlier approach, or how
  the code used to behave.
- **Never describe a past mistake or bug**, or frame the current code as a
  "fix," "correction," or improvement over something that came before.
- Do not use words like *now*, *again*, *still*, *no longer*, *previously*,
  *used to*, or *the old way* to contrast with an earlier state.
- State what the code does and **why it is written this way**, on its own
  terms. If a design choice needs justifying, justify it by the requirement
  it meets, not by the alternative it replaced.

A reference to the Pascal original is not a reference to a prior version of
this code. "Pascal credits the whole move time at departure, so the port
does too" is a present-tense statement of the requirement and is welcome.

Example: instead of "The midpoint test is the cure: the old version drew
moving units at their last node," write "A moving unit is drawn at the
midpoint of its current edge, as the Pascal display does."

---

## American Spelling

Every word in this repository uses American spelling: prose, docstrings,
comments, Markdown, and report text. Never use British spelling.

- `traveled`, `traveling`, `traveler`, `canceled`, `modeled`, `labeled`
  (one `l`), not `travelled`, `cancelled`, `modelled`, `labelled`.
- `color`, `favor`, `behavior`, `neighbor`, `center`, `meter`, `defense`,
  `gray`, `catalog`, `analyze`, `realize`, `recognize`, `organize`,
  `judgment`, `toward`, `while` (not `whilst`), `among` (not `amongst`).
- Library identifiers keep their own spelling, and so does text reproduced
  from the Pascal report, whose wording is part of the fixture.

---

## Dashes

Never use an em dash, an en dash, a minus sign, or any other long dash
character (U+2013, U+2014, U+2212, and their relatives) anywhere: not in
prose, not in comments, docstrings, Markdown, or f-strings. Use a colon, a
comma, parentheses, or a plain hyphen-minus (`-`) instead. Write ranges as
`5 to 14` or `5-14` and negative numbers with the ordinary hyphen.

---

## File Naming

- New files use lowercase `snake_case` with descriptive, topic-based names:
  `test_fasim3.py`, `install_vscode_extensions.ps1`.
- The names inherited from the Pascal project keep their original casing:
  `FASIM3.py`, `SimRun.Doc`, `MinTime.Dat`. They are referenced by that
  spelling in the README, the workspace tasks, and the tests.

---

## Script Structure

Every script begins with a shebang line that runs it through `uv`, so that
on Linux and macOS a script marked executable runs from the command line
with the project's environment and no manual activation. The module
docstring follows on the next line:

```python
#!/usr/bin/env -S uv run python
"""FASIM III: the FASIMNEW model with a Pygame display."""
```

Windows ignores the shebang; there the script runs with
`uv run FASIM3.py`.

Every script must produce visible output. `FASIM3.py` prints the completion
state, the round count, and the full path of the report it wrote. A helper
script added to the repository ends with a short check that exercises what it
defines and prints the result next to the expected answer.

---

## Python Code Style

### Type Hints

- Use type hints for all functions and dataclass fields.
- Prefer modern Python 3.14 syntax:

```python
float | None
list[str]
tuple[int, int]
```

- `from __future__ import annotations` stays at the top of `FASIM3.py` so
  that record types can refer to each other in the linked-list fields.

### Docstrings

- Use **NumPy-style docstrings** for reusable functions.

```python
def ShortestPath(StartNode: int, EndNode: int) -> PathPtr:
    """
    Find the least-cost route between two nodes.

    Parameters
    ----------
    StartNode : int
        Node the route begins at, numbered from 1.
    EndNode : int
        Node the route ends at, numbered from 1.

    Returns
    -------
    PathPtr
        Linked list of `PathRec` from start to end, or None if unreachable.
    """
```

- Short helper functions may use one-line docstrings:

```python
def IntStr(I: int) -> str:
    """Format an integer the way the Pascal report does."""
```

### Formatting and Linting

`pyproject.toml` configures Ruff with a 100-column line length and the
`E4`, `E7`, `E9`, `F`, and `I` rule sets. Run both before finishing a change:

```powershell
uv run ruff check .
uv run ruff format .
```

The VS Code workspace formats on save with Ruff and organizes imports, so a
file edited by hand and a file edited by a tool end up the same.

---

## File Input and Output

The report path is the one deliberate exception to anchoring files to the
script. `--output` defaults to `SimRun.Doc` relative to the current working
directory because it is a user-facing command-line option, and the README
says so. The VS Code launch configurations and tasks set `cwd` to the
project folder so that a run from the editor lands the report there.

Everything else follows the usual rule. A test that reads a fixture anchors
it to the test file:

```python
Fixture = Path(__file__).parent / "fixtures" / "pascal-default.doc"
```

Scratch reports written during development go to a temporary folder or to
the `tmp_path` fixture in pytest, never to the project folder, so that the
`SimRun.Doc` produced by a real run is not overwritten by an experiment.

When a script reports a save, print the full path rather than the bare
name, as `main()` does, so the reader can tell at once where the file went.

---

## Display Code

The Pygame display is a viewer for the model, not part of it. Playback
speed, window size, pausing, and stepping must never change the random
sequence or the event order; a headless run and a graphics run with the
same seed produce identical reports, and a test checks that.

- Layout uses the EGA map's logical 640 by 480 coordinate space. Node
  positions, panel rectangles, and text origins are written in those units
  and mapped to window pixels through `P()` and `L()` at draw time.
- Text is rendered at the window's scale, never rendered small and
  stretched. `SetScale()` rebuilds `Font` and `SmallFont` when the window
  size changes.
- Colors, unit symbols, and the midpoint placement of traveling units follow
  the Pascal display. The unit icons carry their own numbers so that a fire
  unit labeled 3 is not mistaken for node 3.
- The drawing code must run under `SDL_VIDEODRIVER=dummy`. Do not add a
  dependency on a real window, a system font, or an image file.

---

## Testing

```powershell
uv run pytest
```

The tests cover the random-number sequences and distributions, shortest
paths against an independent reference, event ordering, repeatability,
report formatting, the Pascal default-run fixture, and the Pygame controls
and rendering through SDL's dummy video driver.

- A change to the model must keep the fixture comparison passing, or must
  update the fixture with an explanation of the model difference.
- A change to the display must keep the dummy-driver render test passing.
  Extend that test rather than skipping it when the drawing surface changes.
- Tests use the same `PascalCase` naming as the module for fixtures and
  locals, and `test_snake_case` for the test functions pytest collects.

---

## Environment Notes

These are properties of the development setup, not style rules.

- The project requires Python 3.14 and is managed by `uv`. `uv sync` creates
  `.venv` and installs the locked dependencies; the workspace has a task for
  it. Run `uv sync` again after editing `pyproject.toml`.
- The graphics dependency is `pygame-ce`, which provides the `pygame`
  import. Never install the separate `pygame` distribution alongside it;
  they share the same import namespace and the result is unpredictable.
- No Node.js is installed. When a Node tool such as `cspell` is needed from
  a terminal, bootstrap it with `uvx --from "nodejs-bin[cmd]" npx cspell@8`.
  Newer `cspell` releases require a Node version that package does not ship.
- `cspell.json` in the project root lists the project's vocabulary for the
  Code Spell Checker extension. When a new term is legitimately unknown to
  the dictionary, add it there rather than suppressing the checker.
- `install_vscode_extensions.ps1` and `.sh` install the extension set used
  across this and the related QIS101 and Chess Candy workspaces.
