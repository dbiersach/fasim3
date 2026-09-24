import io
import math
import random
from pathlib import Path

import pytest

import FASIM3 as Model


@pytest.fixture(autouse=True)
def CleanState():
    Model.MaxClock = 1000.0
    Model.EventsPerSecond = 25.0
    Model.DataFile = None
    Model.InitModel(5)
    yield
    if Model.DataFile is not None:
        Model.DataFile.close()
        Model.DataFile = None
    if Model.pygame is not None:
        Model.pygame.quit()


def test_uniform_sequence_and_seed_reference():
    Seed = Model.SeedRec(1)
    for Expected in (16807, 282475249, 1622650073, 984943658, 1144108930):
        U1 = Model.Random(Seed, 0)
        assert Seed.Value == Expected
        assert U1 == Expected / 2147483647


def test_normal_and_exponential_transforms():
    Seed = Model.SeedRec(1)
    assert Model.Random(Seed, 2) == pytest.approx(3.2852859526035707)
    assert Seed.Value == 282475249
    Seed = Model.SeedRec(1)
    assert Model.Random(Seed, 1) == -math.log(16807 / 2147483647)
    Seed = Model.SeedRec(314159)
    Values = [Model.Random(Seed, 2) for _ in range(30000)]
    Mean = sum(Values) / len(Values)
    Variance = sum((X - Mean) ** 2 for X in Values) / len(Values)
    assert abs(Mean) < 0.03
    assert abs(Variance - 1) < 0.04


@pytest.mark.parametrize("Seed", [0, -1, 2147483647])
def test_invalid_seed(Seed):
    with pytest.raises(ValueError):
        Model.Random(Model.SeedRec(Seed), 0)


def test_invalid_type_does_not_consume_seed():
    Seed = Model.SeedRec(1)
    with pytest.raises(ValueError):
        Model.Random(Seed, 3)
    assert Seed.Value == 1


def EmptyGraph():
    Model.InitConnAry()
    Model.TravelTime = [[0.0] * 21 for _ in range(21)]


def Edge(I, J, Cost):
    Model.Conn[I][J] = True
    Model.TravelTime[I][J] = Cost


def CheckGraph():
    Expected = [[math.inf] * 21 for _ in range(21)]
    for I in range(1, 21):
        for J in range(1, 21):
            if Model.Conn[I][J]:
                Expected[I][J] = Model.TravelTime[I][J]
        Expected[I][I] = 0.0
    for K in range(1, 21):
        for I in range(1, 21):
            for J in range(1, 21):
                Expected[I][J] = min(Expected[I][J], Expected[I][K] + Expected[K][J])
    for I in range(1, 21):
        for J in range(1, 21):
            Head = Model.ShortestPath(I, J)
            if math.isinf(Expected[I][J]):
                assert Head is None
                continue
            assert Head is not None
            assert Head.NodeID == I
            P, Prev, Cost = Head, None, 0.0
            Seen = set()
            while P is not None:
                assert P.NodeID not in Seen
                Seen.add(P.NodeID)
                assert P.Prev is Prev
                if Prev is not None:
                    assert Model.Conn[Prev.NodeID][P.NodeID]
                    Cost += Model.TravelTime[Prev.NodeID][P.NodeID]
                assert P.TotalTime == pytest.approx(Cost)
                Prev, P = P, P.Next
            assert Prev.NodeID == J
            assert Cost == pytest.approx(Expected[I][J])
            Model.DeletePath(Head)
            assert Head.Next is Head.Prev is None


def test_dijkstra_against_floyd_warshall():
    CheckGraph()
    EmptyGraph()
    CheckGraph()
    for I, J, Cost in [
        (1, 2, 10),
        (1, 3, 1),
        (3, 2, 1),
        (2, 4, 3),
        (3, 4, 100),
        (4, 5, 1500),
        (5, 6, 0),
        (6, 5, 0),
        (3, 7, 4),
        (7, 4, 0),
    ]:
        Edge(I, J, Cost)
    CheckGraph()
    Generator = random.Random(412)
    for _ in range(20):
        EmptyGraph()
        for I in range(1, 21):
            for J in range(1, 21):
                if Generator.random() < 0.2:
                    Edge(I, J, Generator.randrange(4000) / 4)
        CheckGraph()


def test_invalid_graph_and_endpoints():
    assert Model.ShortestPath(0, 1) is None
    assert Model.ShortestPath(1, 21) is None
    Edge(1, 2, -1)
    assert Model.ShortestPath(1, 2) is None
    Edge(1, 2, math.nan)
    assert Model.ShortestPath(1, 2) is None


def test_copy_path_is_independent():
    Path1 = Model.ShortestPath(1, 20)
    Path2 = Model.CopyPath(Path1)
    assert Path1 is not Path2
    First = Path2
    while Path1 is not None:
        assert Path2 is not None
        assert Path1.NodeID == Path2.NodeID
        assert Path1.TotalTime == Path2.TotalTime
        assert Path1 is not Path2
        Path1, Path2 = Path1.Next, Path2.Next
    assert Path2 is None
    Model.DeletePath(First)
    assert Model.CopyPath(None) is None


def test_event_queue_is_stable_and_copies_records():
    Model.EventQ = None
    for Time, UnitID in [(4, 1), (2, 2), (4, 3), (0, 4), (2, 5)]:
        NewEvent = Model.EventRec(Time, Model.FM, UnitID)
        Model.Schedule(NewEvent)
        NewEvent.UnitID = 99
    Got = []
    CEvnt = Model.EventQ
    while CEvnt is not None:
        Got.append((CEvnt.Time, CEvnt.UnitID))
        CEvnt = CEvnt.Next
    assert Got == [(0, 4), (2, 2), (2, 5), (4, 1), (4, 3)]


def test_default_report_matches_pascal_bytes(tmp_path):
    Output = tmp_path / "SimRun.Doc"
    assert Model.main(["--headless", "--output", str(Output)]) == 0
    Expected = Path(__file__).with_name("fixtures") / "pascal-default.doc"
    assert Output.read_bytes() == Expected.read_bytes()
    assert Model.TotalRounds == 2300
    assert Model.Clock > Model.MaxClock
    assert len(Model.FU) == 6 and len(Model.SU) == 3
    for Unit in Model.FU.values():
        assert 0 <= Unit.Sply <= Model.MaxFUSply
    for Unit in Model.SU.values():
        assert 0 <= Unit.Sply <= Model.MaxSUSply
    Second = tmp_path / "second.doc"
    assert Model.main(["--headless", "--output", str(Second)]) == 0
    assert Second.read_bytes() == Output.read_bytes()


def test_negative_rounds_do_not_add_supply(monkeypatch):
    monkeypatch.setattr(Model, "Random", lambda Seed, Typ: -100.0)
    Model.DataFile = io.StringIO()
    Model.ProcFM(Model.EventRec(0.0, Model.FM, 1))
    assert Model.FU[1].Sply == Model.MaxFUSply
    assert Model.TotalRounds == 0
    assert Model.FU[1].TotalTime[Model.Firing] == 0


def test_deadlock_reports_error():
    for Unit in Model.SU.values():
        Unit.Allocated = True
    Model.EventQ = Model.EventRec(0.0, Model.FURQO, 2)
    with pytest.raises(RuntimeError, match="deadlock"):
        Model.ProcFURQO(Model.EventRec(0.0, Model.FURQO, 1))


def test_mintime_export(tmp_path):
    Output = tmp_path / "MinTime.Dat"
    Model.SaveMinTimeAry(Output)
    Values = [float(Line) for Line in Output.read_text().splitlines()]
    assert len(Values) == 210
    Index = 0
    for I in range(1, 21):
        for J in range(I, 21):
            assert Values[Index] == pytest.approx(Model.MinTime[I][J], abs=0.000051)
            Index += 1


def DummyGraphics(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def test_pygame_render_and_controls(monkeypatch):
    DummyGraphics(monkeypatch)
    OriginalInit = Model.InitHardware

    def InitAndPost():
        OriginalInit()
        for Key in (
            Model.pygame.K_SPACE,
            Model.pygame.K_EQUALS,
            Model.pygame.K_MINUS,
            Model.pygame.K_n,
        ):
            Model.pygame.event.post(Model.pygame.event.Event(Model.pygame.KEYDOWN, key=Key))
        Model.pygame.event.post(Model.pygame.event.Event(Model.pygame.QUIT))

    monkeypatch.setattr(Model, "InitHardware", InitAndPost)
    Model.RunGraphics()
    assert Model.Paused
    assert Model.EventsPerSecond == 25
    assert Model.FU[1].NumFM == 1
    assert sum(Unit.NumFM for Unit in Model.FU.values()) == 1
    Model.DrawMap()
    assert Model.Screen.get_size() == (1280, 960)
    assert Model.Canvas is Model.Screen
    assert Model.Scale == 2.0
    assert (Model.OffsetX, Model.OffsetY) == (0, 0)
    assert tuple(Model.Canvas.get_at(Model.P(1, 352)))[:3] == (14, 20, 31)
    assert Model.Canvas.get_bounding_rect().size == (1280, 960)


def test_graphics_and_headless_same_report(tmp_path, monkeypatch):
    DummyGraphics(monkeypatch)
    Headless = tmp_path / "headless.doc"
    Graphics = tmp_path / "graphics.doc"
    assert Model.main(["--headless", "--max-clock", "10", "--output", str(Headless)]) == 0
    assert (
        Model.main(
            [
                "--max-clock",
                "10",
                "--events-per-second",
                "1000",
                "--exit-on-complete",
                "--output",
                str(Graphics),
            ]
        )
        == 0
    )
    assert Graphics.read_bytes() == Headless.read_bytes()


def test_early_graphics_close_writes_statistics(tmp_path, monkeypatch):
    DummyGraphics(monkeypatch)
    OriginalInit = Model.InitHardware

    def InitAndClose():
        OriginalInit()
        Model.pygame.event.post(Model.pygame.event.Event(Model.pygame.QUIT))

    monkeypatch.setattr(Model, "InitHardware", InitAndClose)
    Output = tmp_path / "partial.doc"
    assert Model.main(["--output", str(Output)]) == 0
    assert not Model.Complete
    assert Output.read_text().endswith("Total Number of Rounds Fired: 0\n")


@pytest.mark.parametrize(
    "Args", [["--seed", "0"], ["--max-clock", "nan"], ["--events-per-second", "0"]]
)
def test_cli_rejects_invalid_parameters(Args):
    with pytest.raises(SystemExit) as Error:
        Model.main(Args)
    assert Error.value.code == 2
