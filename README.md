# FASIM III: Field Artillery Simulator

FASIM III is a discrete-event simulation of artillery units fighting a
long battle on a road network. Six fire units shoot at targets, run low on
ammunition, and call for resupply. Three supply units drive out to meet
them, hand over rounds, and go back to a depot when their own trucks are
empty. The program plays the whole thing out on an animated map and then
writes a report that says how every unit spent its time and how many rounds
were fired in total.

The point of the exercise is the last number. An artillery battery only
matters when it is firing, and every hour it spends driving, waiting, or
loading ammunition is an hour it is not firing. The simulation lets you ask
questions like these and get an answer in minutes instead of in the field:

- Should a supply truck drive to where the guns are now, or to where they
  are about to move?
- Should the two units meet somewhere along the guns' route instead?
- What happens to total output if the depot is moved, if there are more
  trucks, or if the trucks are faster?
- How much time do the guns lose waiting for ammunition, and which units
  wait the most?

Changing a few constants at the top of `FASIM3.py` changes the answer, and
the report tells you whether the change helped.

## What "discrete-event simulation" means

A video game moves everything forward a tiny slice of time at a time, sixty
times a second, whether anything interesting is happening or not. A
discrete-event simulation does the opposite. It keeps a list of future
events, each stamped with the moment it will happen, and it jumps the clock
straight from one event to the next. Nothing changes between events, so
there is nothing to compute there.

FASIM III has eleven kinds of event. A fire unit starts a mission, a fire
unit finishes one, a unit departs a node, a unit arrives at a node, two
units link up and begin resupply, and so on. Handling one event usually
schedules one or two more. Starting a fire mission schedules its end;
arriving at a node schedules the departure for the next one. The event
queue is a linked list kept in time order, and the main loop simply pops
the earliest event, advances the clock to its time, and runs the matching
handler until the clock passes 1000 time units.

Because each event is processed in strict time order, the whole run is
deterministic. Give the program the same seed and it produces the same
battle, event for event, whether it draws the map or not.

## The battlefield

The map is a network of 20 nodes scattered at random across a 640 by 480
grid. You can think of the nodes as towns or crossroads. Each node is
connected to its three nearest neighbors, measured by travel time, and the
connections run in both directions, so the result is a road network with
loops and dead ends rather than a neat grid. Node 1 is special: it is the
ammunition transfer point, or ATP, the depot where supply trucks refill.

Travel time along a road is its straight-line length times a distance
factor. Fire units are slow and supply units are about two and a half times
faster, so the same road takes each kind of unit a different amount of
time.

Units never cut across country. They move from node to node along the
network, and to get anywhere they need a route.

## Finding the shortest route

Whenever a unit is ordered somewhere, the program runs Dijkstra's
algorithm from its current node. Dijkstra's algorithm is the standard way
to find the cheapest path through a weighted graph. It keeps a set of nodes
whose best distance is settled, repeatedly picks the unsettled node with
the smallest tentative distance, settles it, and relaxes the distances of
its neighbors. When the destination is settled, the algorithm follows the
predecessor links backward to build the route as a linked list of nodes,
each carrying the cumulative travel time to reach it.

The same algorithm is run once for every pair of nodes at startup to fill
a 20 by 20 table of minimum travel times. That table is what the decision
logic consults when it compares possible meeting places, because looking up
a number is far cheaper than rebuilding a route each time the question
comes up.

## The units

**Fire units** are the guns. Each one starts with a full load of 373
rounds, a random starting node, and a fire mission scheduled at time zero.
A mission fires a number of rounds drawn from a normal distribution with a
mean of 14 and a standard deviation of 4, capped at whatever the unit still
has. Firing runs at four rounds per time unit, so the mission's duration
follows from its size. After a mission the unit waits a random interval,
exponentially distributed with a mean of 10, and fires again.

Firing has a cost beyond ammunition. Each mission raises the unit's
detection score by an amount that depends on how far the mission strayed
from the average size. When that score crosses 0.9, the enemy is assumed to
have located the battery and it must move to a new node, chosen at random.
Moving resets the score to zero.

**Supply units** are the trucks. Each starts with 333 rounds at a random
node, waiting to be called. A truck can be allocated to only one fire unit
at a time. When a truck's load drops below about 20 percent of capacity it
drives to the ATP at node 1, refills completely, and becomes available
again.

## Asking for resupply

After every mission a fire unit checks two things: whether its detection
score is too high and whether its ammunition has dropped below about 21
percent of a full load. If either is true, it requests orders. This is the
heart of the simulation.

The request handler first settles where the fire unit is going. If it has
no destination it picks a new node at random and computes the shortest
route there. Then, for every supply truck that is not already allocated, it
evaluates three possible rendezvous plans:

- **Type I, initial.** The truck drives to the fire unit's current node and
  resupplies it there before it moves.
- **Type F, final.** Both units head for the fire unit's destination and
  meet there.
- **Type P, point.** The two units meet at some intermediate node on the
  fire unit's route. The handler checks every node on the route and keeps
  the one both units can reach soonest.

For each plan the meeting time is the larger of the two units' travel
times, because the resupply cannot start until both have arrived. A fire
unit whose detection score is too high is never asked to sit still for a
type I meeting. The constant `Alpha` weighs unit resupply against point
resupply; at its default of zero the unit plans win, and raising it makes
the program favor meeting along the way. The truck and plan with the
earliest meeting time get the job.

If every truck is busy, the request is put back on the queue just after
the next event that might free one, and the fire unit keeps trying.

## Resupply and the return to the depot

When both units are at the meeting node they link up. Transfer speed
depends on the plan: three rounds per time unit for a unit-to-unit meeting
and four for a point meeting. The transfer lasts as long as it takes to
fill the fire unit's shortfall, after which the truck hands over whatever
it can. If the truck runs dry it gives what it has. A truck that ends up
below its threshold heads straight for the ATP; otherwise it is released
and waits for the next call. The fire unit, now restocked, continues to its
destination or schedules its next mission.

## Random numbers you can reproduce

Everything random in the simulation comes from one generator, the
Park-Miller "minimal standard" linear congruential generator. It multiplies
the current seed by 16807, takes the remainder modulo 2^31 - 1, and uses
Schrage's method to do that without overflowing a 32-bit integer. The
result divided by the modulus is a uniform number between 0 and 1.

From that one uniform stream the program derives the other distributions
it needs. An exponential value for the gaps between missions comes from
`-ln(u)`. A normal value for mission size comes from the Box-Muller
transform, which turns two uniforms into one standard normal using a square
root, a logarithm, and a cosine.

The seed is the only source of randomness. The default is 5, and the
`--seed` option changes it. Two runs with the same seed produce identical
node layouts, identical unit placements, identical mission sizes, and
identical reports, which is what makes it possible to change one constant
and attribute the difference in the results to that change alone.

## The animation

Running the program opens a window that draws the network and the units as
the battle unfolds:

- Nodes are red circles with their numbers above them.
- Roads are blue lines.
- Fire units are yellow gun symbols with the unit's number below.
- Supply units are green truck symbols with the unit's number below.
- A unit in transit is drawn at the midpoint of the road it is on.

The top line shows the simulation clock, the running total of rounds fired,
and whether the run is paused. The panel at the bottom shows the four most
recent lines of the event log, so you can read what just happened while
you watch the map. The window is resizable and the map scales to fit.

Keyboard controls:

- **Space** pauses or resumes.
- **N** or **Right Arrow** advances one event and pauses.
- **+ / -** raises or lowers the playback rate in events per second.
- **Esc** or the window's close button exits.

Playback speed and window size only affect what you see. They never change
the random sequence or the order of events, so a run watched slowly and a
run watched at full speed are the same battle.

## The output report

Every run writes `SimRun.Doc`, a plain text file. The first part is the
event log, one line per event, each stamped with the clock time:

```text
Clock:233.5077-> Fire Mission! FU:5(14) Rounds:19
Clock:233.5077-> FU:3(16) Orders> No free SUs! Resch FURQO at 235.7707
Clock:235.7707-> SU:1(18) depart for Node:16 Arrive:245.2548
Clock:245.2548-> FU:3(16) and SU:1(16) linked. -> Begin Resupply
```

The notation `FU:5(14)` means fire unit 5 at node 14. The log records
every mission, every request for orders and the plan it chose, every
departure and arrival, every resupply, and every trip to the depot.

The second part is the statistics. For each fire unit and each supply unit
the report lists the total time spent in each of six states:

| State         | Meaning                                                    |
| ------------- | ---------------------------------------------------------- |
| Firing        | Executing a fire mission                                   |
| Moving        | Traveling between nodes                                    |
| URSupplying   | Transferring ammunition at a unit-to-unit rendezvous       |
| PRSupplying   | Transferring ammunition at a point rendezvous              |
| FMWaiting     | Idle between missions with ammunition on hand              |
| SplyWaiting   | Waiting at the meeting node for the other unit to arrive   |

Each fire unit's entry ends with its number of missions and each supply
unit's entry with its number of resupply runs. The file closes with the
number that the whole exercise is about:

```text
Total Number of Rounds Fired: 2300
```

Compare that figure across runs to see whether a change to the supply plan
made the battery more or less productive.

## Experimenting

The constants at the top of `FASIM3.py` are the knobs. A few worth turning:

- `MaxSU` and `MaxFU` change how many trucks serve how many guns.
- `MaxFUSpeed` and `MaxSUSpeed` change how fast each kind of unit moves.
- `MinAccFUSply` and `MinAccSUSply` set the ammunition levels at which a
  gun asks for resupply and a truck returns to the depot.
- `UnitResplyRate` and `PointResplyRate` set how fast ammunition transfers.
- `Alpha` shifts the choice between unit and point rendezvous.
- `MaxFUPDetect` sets how long a battery can keep firing before it must move.

Run the same seed before and after a change, and compare the total rounds
and the waiting times. Then try several seeds, because a single map can
favor one plan by accident.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
open `FASIM3.code-workspace` in VS Code. Accept its recommended Python and
Ruff extensions. In the workspace terminal, run:

```powershell
uv sync
uv run FASIM3.py
```

`uv sync` creates `.venv`, installs Python 3.14 if needed, and installs the
locked dependencies. The graphics dependency is `pygame-ce`, which supplies
Python 3.14 wheels and the `pygame` import. Do not install the separate
`pygame` distribution alongside it; they share the same import namespace.

The workspace includes Pygame and headless debug configurations for F5,
plus tasks for syncing, running, testing, and linting. Select `.venv`
through **Python: Select Interpreter** if VS Code already remembers another
interpreter.

## Running

```powershell
uv run FASIM3.py
uv run FASIM3.py --headless
uv run FASIM3.py --events-per-second 100 --exit-on-complete
uv run FASIM3.py --seed 5 --max-clock 1000 --output trial.doc
```

`--headless` runs the model without opening a window, which is the fastest
way to generate a report. `--seed` selects the random sequence,
`--max-clock` sets the simulation horizon, and `--output` names the report
file. The default output path is `SimRun.Doc` in the current working
directory; the VS Code configurations use the project directory.

The window stays open after the run completes. Closing it early saves the
statistics accumulated so far, and the terminal reports that the run
stopped early. Running again replaces `SimRun.Doc`, so use `--output` to
keep separate reports.

Some seeds produce a network in which a node cannot reach every other node.
The program detects this and stops with a clear error rather than running a
broken battle. A queue containing only unresolvable requests also stops
explicitly.

## Development

```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
```

The tests cover the random-number generator and its distributions, the
shortest-path routine against an independent reference, event ordering,
repeatability from a fixed seed, report formatting, a full default run
against a recorded fixture, and the Pygame controls and rendering through
SDL's dummy video driver. `AGENTS.md` describes the coding conventions the
repository follows.

## License

This project is released under the BSD 3-Clause License. See `LICENSE`.
