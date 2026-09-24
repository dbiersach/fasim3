# FASIM III: Field Artillery Simulator

FASIM III is a discrete-event simulation of artillery units fighting a
long battle on a road network. Six fire units shoot at targets, run low on
ammunition or draw too much attention, and call for orders. Three supply
units drive out to meet them, hand over rounds, and go back to a depot when
their own load falls below about 20 percent. The program plays the whole
thing out on an animated map and then writes a report with activity
counters for every unit and the total number of rounds fired.

The point of the exercise is the last number. A gun only contributes when
it is firing, and every hour it spends driving, waiting, or loading
ammunition is an hour it is not firing. The simulation lets you ask
questions like these and get an answer in minutes instead of in the field:

- Should a supply truck drive to where the guns are now, or to where they
  are about to move?
- Should the two units meet somewhere along the guns' route instead?
- What happens to total output if there are more trucks, if the trucks are
  faster, or if the guns can stay in place longer?
- How often do the guns end up waiting for a truck?

Changing a few constants at the top of `FASIM3.py` changes the answer, and
the report tells you whether the change helped. Total rounds fired is the
model's measure of throughput. It says nothing about what the rounds hit,
so it is a measure of how busy the guns were kept, not of how effective
they were.

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
handler.

The run stops after the first event whose time is beyond the horizon of
1000 time units, so the final clock in a report is slightly past 1000. An
activity that starts near the end is credited in full when it is scheduled,
even if part of it lies past the horizon.

Because each event is processed in strict time order, the whole run is
deterministic. Give the program the same seed and it produces the same
battle, event for event, whether it draws the map or not.

## The battlefield

The map is a network of 20 nodes scattered at random across the map area,
which spans x coordinates 10 through 629 and y coordinates 30 through 339
of a 640 by 480 logical display. You can think of the nodes as towns or
crossroads. Each node is connected to its three nearest neighbors, measured
by travel time, and every connection runs in both directions. Because a
node can also be one of another node's three nearest, some nodes end up
with four or five roads, but none has fewer than three, so there are no
dead ends.

Node 1 is special: it is the ammunition transfer point, or ATP, the depot
where supply trucks refill. Nothing on the map marks it, which is why the
legend line above the event log always reads `Node 1: ATP`. The depot's
location is fixed in the two handlers that send a truck home and refill
it; it is not one of the constants at the top of the file.

Travel time along a road is its straight-line length times a distance
factor. That number is a route cost shared by both kinds of unit. When a
unit actually moves, the cost is divided by its speed, and supply units are
about two and a half times faster than fire units, so the same road takes
each kind of unit a different amount of time.

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
each carrying the cumulative route cost to reach it.

The same algorithm is run once for every pair of nodes at startup to fill
a 20 by 20 table of minimum route costs. That table is what the decision
logic consults when it compares possible meeting places, because looking up
a number is far cheaper than rebuilding a route each time the question
comes up.

## The units

**Fire units** are the guns. Each one starts with a full load of 373
rounds, a random starting node, and a fire mission scheduled at time zero.
A mission fires a whole number of rounds based on a normal draw with a mean
of 14 and a spread of 4, truncated to an integer and clamped between zero
and whatever the unit still has. Firing runs at four rounds per time unit,
so the mission's duration follows from its size. After a mission the unit
waits a whole number of time units based on an exponential draw with a
mean of 10, and fires again. Because both draws are truncated to integers,
the actual values are not exactly the named continuous distributions.

Firing has a cost beyond ammunition. Each mission raises the unit's
detection score by the size of the mission's deviation from the mean,
divided by the mean. A mission of exactly average size adds nothing. This
score is a simple heuristic that stands in for the enemy noticing a
battery; there is no simulated enemy, no attack, and no losses. When the
score crosses 0.9 the unit is considered located and must move to a new
node, chosen at random. Moving resets the score to zero.

**Supply units** are the trucks. Each starts with 333 rounds at a random
node, waiting to be called. A truck can be allocated to only one fire unit
at a time. When a truck's load drops below about 20 percent of capacity
after a transfer, it goes to the ATP at node 1, refills completely, and
becomes available again.

The program does not say what a "fire unit" or "supply unit" stands for in
real terms. A fire unit might be one gun, a section, or a whole battery,
and a supply unit is a modeled resource rather than a particular truck.
Treat both as abstract units.

## Asking for orders

After every mission a fire unit checks two things: whether its detection
score is above 0.9 and whether its ammunition has dropped below about 21
percent of a full load. If either is true, it requests orders. This is the
heart of the simulation.

Both triggers lead to the same handler, and that handler always pairs the
fire unit with a truck. A unit that has been detected but still has plenty
of ammunition therefore does not simply move; it is assigned a truck and a
meeting place first, and if every truck is busy it keeps re-requesting
orders while sitting where it was detected. In the default run this is the
common case: every request is triggered by detection rather than by
low ammunition.

The handler first settles where the fire unit is going. If it has no
destination it picks a new node at random and computes the shortest route
there. Then, for every truck that is not already allocated, it evaluates
three possible rendezvous plans:

- **Type I, initial.** The truck drives to the fire unit's current node and
  resupplies it there before it moves. This plan is skipped for a unit
  whose detection score is too high.
- **Type F, final.** Both units head for the fire unit's destination and
  meet there.
- **Type P, point.** The two units meet at a node on the fire unit's
  route. The candidates are every node on the route except the final
  destination. The starting node is included unless the unit has been
  detected. The handler keeps the candidate both units can reach soonest.

For each plan the meeting cost is the larger of the two units' route
costs, because the resupply cannot start until both have arrived. The
comparison uses the raw route costs from the table, not the costs divided
by each unit's speed. Since trucks move about two and a half times faster
than guns, the plan with the lowest raw cost is not always the one with the
earliest real meeting time. This is a deliberate simplification: the
selection is a route-cost heuristic, not an exact minimization of arrival
time.

The constant `Alpha` weighs the unit plans (I and F) against the point
plan (P). At its default of zero the unit plans always win, so point
resupply never happens in a default run and the report's point-resupply
counters stay at zero. Raising `Alpha` makes the program favor meeting
along the way. Among the trucks, the one whose chosen plan has the lowest
cost gets the job.

Candidate costs are compared against the simulation horizon as a starting
bound, so a plan whose cost is not strictly below the horizon is never
accepted. With the default map and horizon that never matters, but a very
short `--max-clock` can leave a free truck unassigned.

If no truck can be assigned, the request is rescheduled a tiny fraction
after the next event in the queue that is not itself an orders request.
That event does not necessarily free a truck, so a fire unit may retry many
times before it is served.

## Resupply and the return to the depot

When both units are at the meeting node they link up. Transfer speed
depends on the plan: three rounds per time unit for a unit-to-unit meeting
and four for a point meeting. The transfer duration is the fire unit's
entire shortfall divided by that rate, and it is fixed at the start. Only
when the transfer ends does the truck's own load come into play: it hands
over the shortfall if it can, or everything it has left if it cannot. A
partial delivery therefore takes as long as a full one. Keep this
convention in mind when comparing truck capacities, because it makes
small trucks look slower than a pure transfer-rate model would.

A truck that ends the transfer below its threshold heads straight for the
ATP; otherwise it is released and waits, wherever it is, for the next call.
The fire unit, now restocked, continues to its destination or schedules
its next mission.

The trip to the depot is not simulated node by node like the outbound trip.
The program schedules a single arrival event using the shortest route cost
to node 1 divided by the truck's speed, hides the truck from the map in the
meantime, and on arrival places it at node 1 with a full load. The depot
has unlimited ammunition, loading takes no time, and there is no queue.
This return trip is not added to the truck's moving-time counter.

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
`--seed` option changes it. Two runs with the same seed and the same
constants produce identical node layouts, identical unit placements,
identical mission sizes, and identical reports.

Changing a constant is a different matter. Every random draw comes from
the same stream, so a change that alters the order of events also alters
which draw goes to which decision. The map and the starting positions stay
the same for a given seed, but the mission sizes and intervals after the
first divergence do not. A comparison of one seed before and after a change
is a fair comparison of two battles, not of the same battle with one thing
different.

## The animation

Running the program opens a window that draws the network and the units as
the battle unfolds:

- Nodes are red circles with their numbers above them.
- Roads are blue lines.
- Fire units are yellow gun symbols with the unit's number below.
- Supply units are green truck symbols with the unit's number below.
- A unit in transit is drawn at the midpoint of the road it is on.
- A truck on its way to the depot is not drawn until it reappears at
  node 1.

The top line shows the simulation clock, the running total of rounds fired,
and whether the run is paused. The panel at the bottom starts with a legend
line, `Yellow: fire units (6 total)  Green: supply units (3 total)
Node 1: ATP`, which reminds you what the colors mean, how many of each unit
the model has, and which node is the depot. A truck that is on its way to
the depot is not drawn, so the map can show fewer trucks than the total.
Below it are the four most recent lines of the event log, so you can read
what just happened while you watch the map. The window is resizable and
the map scales to fit.

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
event log, each line stamped with the clock time:

```text
Clock:233.5077-> Fire Mission! FU:5(14) Rounds:19
Clock:233.5077-> FU:3(16) Orders> No free SUs! Resch FURQO at 235.7707
Clock:235.7707-> SU:1(18) depart for Node:16 Arrive:245.2548
Clock:245.2548-> FU:3(16) and SU:1(16) linked. -> Begin Resupply
```

The notation `FU:5(14)` means fire unit 5 at node 14. The log records
every mission, every request for orders and the plan it chose, every
departure, every resupply, and every trip to the depot. It is not exactly
one line per event: an arrival that immediately schedules the next
departure logs only the departure, and an end of mission that trips both
triggers logs a line for each.

The second part is the statistics. For each fire unit and each supply unit
the report lists a time counter for each of six states:

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
made the guns more or less productive.

### Reading the counters carefully

The six state times are activity counters, not a complete account of where
each unit's time went. They do not add up to the length of the run, and
they are not meant to. In the default run, fire unit 3's six counters sum
to about 408 time units out of a run of just over 1000. Several kinds of
time are simply not counted:

- Time spent repeatedly re-requesting orders while every truck is busy.
- Some of the idle time before a mission, in particular after a resupply
  or after arriving at a new node, is scheduled without being added to
  `FMWaiting`.
- A truck's trip back to the depot.
- Any wait still open when the run ends.

Durations are also credited when an activity is scheduled, not when it
completes, so a mission or move that starts near the end of the run counts
in full. Use the counters to compare runs with one another, and use the
mission and resupply counts and the total rounds as the primary results.
Do not divide a counter by the run length and call it a utilization
percentage, and do not read a zero in `SplyWaiting` as proof that a unit
never waited for a truck.

## Experimenting

The constants at the top of `FASIM3.py` are the knobs. A few worth turning:

- `MaxSU` and `MaxFU` change how many trucks serve how many guns.
- `MaxFUSpeed` and `MaxSUSpeed` change how fast each kind of unit moves.
- `MinAccFUSply` and `MinAccSUSply` set the ammunition levels at which a
  gun asks for resupply and a truck returns to the depot.
- `UnitResplyRate` and `PointResplyRate` set how fast ammunition transfers.
- `Alpha` shifts the choice between unit and point rendezvous. It must be
  raised above zero for the point plan to be chosen at all.
- `MaxFUPDetect` sets how long a gun can keep firing before it must move.

Run several seeds for each configuration and compare the spread of total
rounds, not just one number, because a single map can favor one plan by
accident and because a changed constant reshuffles the random draws, as
described above.

## What the model leaves out

FASIM III is a study of one idea, mobile resupply that meets the guns
where they are or where they are going, and it keeps everything else
simple. The following are assumptions, not findings:

- Fire units relocate to a random node rather than to a chosen position.
- One low-ammunition threshold and one detection threshold apply to every
  fire unit.
- Being detected always leads to a resupply pairing, even with ammunition
  to spare.
- The detection score depends only on mission size, not on time in place,
  terrain, or enemy activity.
- Trucks are always about two and a half times faster than guns, on every
  road.
- The depot never runs out and loads a truck instantly.
- Transfer rates are constant regardless of equipment or conditions.
- All six fire units are identical, and so are all three trucks.

Those simplifications make the model easy to reason about and fast to
run. They also mean that a result here is a statement about the model, and
turning it into a statement about real artillery would require deciding
what the units represent and checking the assumptions against real
equipment and practice.

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
