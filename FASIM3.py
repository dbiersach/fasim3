#!/usr/bin/env -S uv run python
"""FASIM III: the FASIMNEW model with a Pygame display."""

from __future__ import annotations

import argparse
import math
import os
import sys
from collections import deque
from dataclasses import dataclass, field, replace
from enum import IntEnum
from pathlib import Path as FilePath
from typing import TextIO

MaxNode = 20
MinConn = 3
DistAdj = 0.051471
MaxFU = 6
MaxFUSply = 373
MinAccFUSply = 0.2105
MaxSU = 3
ATPNode = 1
MaxSUSply = 333
MinAccSUSply = 0.1997
MaxFUPDetect = 0.9
UnitResplyRate = 3
PointResplyRate = 4
MaxFUSpeed = 0.2083
MaxSUSpeed = 0.5208
MeanFMInterval = 10
MeanFMRounds = 14
MaxFireRate = 4
STDFMRounds = 4
Alpha = 0.0
MaxClock = 1000.0

DefTextClr = (85, 255, 255)
DefHiLiteClr = (255, 255, 255)
DefNodeClr = (255, 85, 85)
DefArcClr = (85, 85, 255)
DefFUClr = (255, 255, 85)
DefSUClr = (85, 255, 85)


class UnitStatusType(IntEnum):
    Firing = 0
    Moving = 1
    URSupplying = 2
    PRSupplying = 3
    FMWaiting = 4
    SplyWaiting = 5


Firing, Moving, URSupplying, PRSupplying, FMWaiting, SplyWaiting = UnitStatusType


class EventType(IntEnum):
    FM = 0
    EOM = 1
    FURQO = 2
    FUDN = 3
    SUDN = 4
    FUAN = 5
    SUAN = 6
    SRS = 7
    ERS = 8
    SATP = 9
    EATP = 10


FM, EOM, FURQO, FUDN, SUDN, FUAN, SUAN, SRS, ERS, SATP, EATP = EventType


@dataclass(slots=True)
class SeedRec:
    Value: int = 5


@dataclass(slots=True, eq=False)
class PathRec:
    NodeID: int
    TotalTime: float = 0.0
    Prev: PathRec | None = None
    Next: PathRec | None = None


PathPtr = PathRec | None
StatusTimeAry = dict[UnitStatusType, float]


def StatusTimes() -> StatusTimeAry:
    return {StatusTyp: 0.0 for StatusTyp in UnitStatusType}


@dataclass(slots=True)
class FURec:
    Sply: int = MaxFUSply
    Loc: int = 0
    ReSplyLoc: int = 0
    ReSplySU: int = 0
    NumFM: int = 0
    ReSplyTyp: str = "\0"
    SplyWaitClock: float = 0.0
    PDetect: float = 0.0
    Dstn: PathPtr = None
    Status: UnitStatusType = FMWaiting
    TotalTime: StatusTimeAry = field(default_factory=StatusTimes)


@dataclass(slots=True)
class SURec:
    Sply: int = MaxSUSply
    Loc: int = 0
    ReSplyLoc: int = 0
    ReSplyFU: int = 0
    NumSM: int = 0
    SplyWaitClock: float = 0.0
    Dstn: PathPtr = None
    Status: UnitStatusType = SplyWaiting
    TotalTime: StatusTimeAry = field(default_factory=StatusTimes)
    Allocated: bool = False


@dataclass(slots=True)
class NodeRec:
    X: int = 0
    Y: int = 0
    PDetectAdj: float = 1.0


@dataclass(slots=True)
class ArcRec:
    SpeedAdj: float = 1.0


@dataclass(slots=True, eq=False)
class EventRec:
    Time: float
    Typ: EventType
    UnitID: int
    Next: EventRec | None = None


EventPtr = EventRec | None
FUAry = dict[int, FURec]
SUAry = dict[int, SURec]
NodeAry = dict[int, NodeRec]
ArcAry = list[list[ArcRec]]
TimeAry = list[list[float]]
ConnAry = list[list[bool]]

Node: NodeAry = {}
TravelTime: TimeAry = []
MinTime: TimeAry = []
Conn: ConnAry = []
Arc: ArcAry = []
FU: FUAry = {}
SU: SUAry = {}
EventQ: EventPtr = None
Gap = Issued = TotalRounds = 0
RNFSeed = SeedRec()
Clock = 0.0
DataFile: TextIO | None = None

LastLines: deque[str] = deque(maxlen=4)
Screen = Canvas = Font = SmallFont = pygame = None
Scale = 1.0
OffsetX = OffsetY = 0
AtATP: set[int] = set()
Complete = False
Paused = False
EventsPerSecond = 25.0


def Random(Seed: SeedRec, Typ: int) -> float:
    A, M, Q, R = 16807, 2147483647, 127773, 2836
    if not 1 <= Seed.Value < M:
        raise ValueError("Seed must be in 1..2147483646")
    if Typ not in (0, 1, 2):
        raise ValueError("Typ must be 0 (uniform), 1 (exponential), or 2 (normal)")
    Hi, Lo = divmod(Seed.Value, Q)
    Test = A * Lo - R * Hi
    Seed.Value = Test if Test > 0 else Test + M
    U1 = Seed.Value / M
    if Typ == 0:
        return U1
    if Typ == 1:
        return -math.log(U1)
    Hi, Lo = divmod(Seed.Value, Q)
    Test = A * Lo - R * Hi
    Seed.Value = Test if Test > 0 else Test + M
    U2 = Seed.Value / M
    return math.sqrt(-2 * math.log(U1)) * math.cos(2 * math.pi * U2)


def IntStr(I: int) -> str:
    return str(I)


def RealStr(R: float) -> str:
    return f"{R:.4f}"


def FUStr(FUn: int) -> str:
    return f"FU:{FUn}({FU[FUn].Loc})"


def SUStr(SUn: int) -> str:
    return f"SU:{SUn}({SU[SUn].Loc})"


def PrintLine(WkStr: str) -> None:
    Line = "Clock:" + RealStr(Clock) + "-> " + WkStr
    LastLines.append(Line)
    if DataFile is not None:
        DataFile.write(Line + "\n")


def InitNodeAry() -> None:
    for NodeNum in range(1, MaxNode + 1):
        Node[NodeNum] = NodeRec(
            math.trunc(Random(RNFSeed, 0) * 620) + 10,
            math.trunc(Random(RNFSeed, 0) * 310) + 30,
            1.0,
        )


def InitArcAry() -> None:
    global Arc
    Arc = [[ArcRec() for _ in range(MaxNode + 1)] for _ in range(MaxNode + 1)]


def InitConnAry() -> None:
    global Conn
    Conn = [[False] * (MaxNode + 1) for _ in range(MaxNode + 1)]


def InitTravelTimeAry() -> None:
    global TravelTime
    TravelTime = [[0.0] * (MaxNode + 1) for _ in range(MaxNode + 1)]
    for SNode in range(1, MaxNode + 1):
        for ENode in range(SNode, MaxNode + 1):
            TravelTime[SNode][ENode] = (
                math.sqrt(
                    (Node[SNode].X - Node[ENode].X) ** 2 + (Node[SNode].Y - Node[ENode].Y) ** 2
                )
                * DistAdj
                * Arc[SNode][ENode].SpeedAdj
            )
            TravelTime[ENode][SNode] = TravelTime[SNode][ENode]


def ConnNodes() -> None:
    for SNode in range(1, MaxNode + 1):
        SortNode = sorted(
            range(1, MaxNode + 1),
            key=lambda ENode: Arc[SNode][ENode].SpeedAdj * TravelTime[SNode][ENode],
        )
        for ENode in range(1, MinConn + 1):
            Conn[SNode][SortNode[ENode]] = True
            Conn[SortNode[ENode]][SNode] = True


def InitFUAry() -> None:
    FU.clear()
    Empty = [True] * (MaxNode + 1)
    for UnitNum in range(1, MaxFU + 1):
        while True:
            Loc = math.trunc(Random(RNFSeed, 0) * MaxNode) + 1
            if Empty[Loc]:
                break
        Empty[Loc] = False
        FU[UnitNum] = FURec(Loc=Loc, Dstn=PathRec(Loc))


def InitSUAry() -> None:
    SU.clear()
    Empty = [True] * (MaxNode + 1)
    for UnitNum in range(1, MaxSU + 1):
        while True:
            Loc = math.trunc(Random(RNFSeed, 0) * MaxNode) + 1
            if Empty[Loc]:
                break
        Empty[Loc] = False
        SU[UnitNum] = SURec(Loc=Loc, Dstn=PathRec(Loc))


def InitEventQ() -> None:
    global EventQ
    EventQ = None
    for FUNum in range(1, MaxFU + 1):
        Schedule(EventRec(0.0, FM, FUNum))


def DeletePath(Path: PathPtr) -> None:
    while Path is not None:
        NextPath = Path.Next
        Path.Prev = Path.Next = None
        Path = NextPath


def CopyPath(Path1: PathPtr) -> PathPtr:
    Path2 = CPath2 = None
    while Path1 is not None:
        NPath2 = PathRec(Path1.NodeID, Path1.TotalTime, Prev=CPath2)
        if CPath2 is None:
            Path2 = NPath2
        else:
            CPath2.Next = NPath2
        CPath2 = NPath2
        Path1 = Path1.Next
    return Path2


def ShortestPath(StartNode: int, EndNode: int) -> PathPtr:
    if not 1 <= StartNode <= MaxNode or not 1 <= EndNode <= MaxNode:
        return None
    Dist = [0.0] * (MaxNode + 1)
    Pred = [0] * (MaxNode + 1)
    Reached = [False] * (MaxNode + 1)
    Settled = [False] * (MaxNode + 1)
    for I in range(1, MaxNode + 1):
        for J in range(1, MaxNode + 1):
            if Conn[I][J] and (TravelTime[I][J] < 0 or not math.isfinite(TravelTime[I][J])):
                return None
    Reached[StartNode] = True
    while True:
        Best = 0
        for I in range(1, MaxNode + 1):
            if Reached[I] and not Settled[I]:
                if Best == 0 or Dist[I] < Dist[Best]:
                    Best = I
        if Best == 0:
            break
        Settled[Best] = True
        if Best == EndNode:
            break
        for J in range(1, MaxNode + 1):
            if Conn[Best][J] and not Settled[J]:
                Candidate = Dist[Best] + TravelTime[Best][J]
                if not Reached[J] or Candidate < Dist[J]:
                    Dist[J], Pred[J], Reached[J] = Candidate, Best, True
    if not Settled[EndNode]:
        return None
    Head = None
    Current = EndNode
    while Current != 0:
        NewPath = PathRec(Current, Dist[Current], Next=Head)
        if Head is not None:
            Head.Prev = NewPath
        Head = NewPath
        Current = Pred[Current]
    return Head


def RequirePath(Path: PathPtr) -> PathRec:
    if Path is None:
        raise RuntimeError("The model requires a connected graph and a valid route")
    return Path


def InitMinTimeAry() -> None:
    global MinTime
    MinTime = [[0.0] * (MaxNode + 1) for _ in range(MaxNode + 1)]
    for SNode in range(1, MaxNode + 1):
        for ENode in range(1, MaxNode + 1):
            Path = ShortestPath(SNode, ENode)
            if Path is None:
                raise RuntimeError(f"No valid route from node {SNode} to {ENode}")
            Tail = Path
            while Tail.Next is not None:
                Tail = Tail.Next
            MinTime[SNode][ENode] = Tail.TotalTime
            DeletePath(Path)


def SaveMinTimeAry(Filename: str | FilePath = "MinTime.Dat") -> None:
    with open(Filename, "w", encoding="ascii", newline="\r\n") as DataFile:
        for SNode in range(1, MaxNode + 1):
            for ENode in range(SNode, MaxNode + 1):
                DataFile.write(f"{MinTime[SNode][ENode]:10.4f}\n")


def Schedule(NewEvent: EventRec) -> None:
    global EventQ
    NEvnt = replace(NewEvent, Next=None)
    if EventQ is None or NewEvent.Time < EventQ.Time:
        NEvnt.Next = EventQ
        EventQ = NEvnt
        return
    CEvnt = EventQ
    while CEvnt.Next is not None and NewEvent.Time >= CEvnt.Next.Time:
        CEvnt = CEvnt.Next
    NEvnt.Next = CEvnt.Next
    CEvnt.Next = NEvnt


def ProcFM(CurEvent: EventRec) -> None:
    global TotalRounds
    FUn = CurEvent.UnitID
    Unit = FU[FUn]
    Unit.Status = Firing
    Unit.NumFM += 1
    NumFMRounds = math.trunc(Random(RNFSeed, 2) * STDFMRounds) + MeanFMRounds
    NumFMRounds = min(max(NumFMRounds, 0), Unit.Sply)
    Duration = NumFMRounds / MaxFireRate
    Unit.TotalTime[Firing] += Duration
    Unit.Sply -= NumFMRounds
    Unit.PDetect += abs(NumFMRounds - MeanFMRounds) / MeanFMRounds * Node[Unit.Loc].PDetectAdj
    PrintLine("Fire Mission! " + FUStr(FUn) + " Rounds:" + IntStr(NumFMRounds))
    TotalRounds += NumFMRounds
    NewEvent = EventRec(Clock + Duration, EOM, FUn)
    Schedule(NewEvent)


def ProcEOM(CurEvent: EventRec) -> None:
    FUn = CurEvent.UnitID
    Unit = FU[FUn]
    Unit.Status = FMWaiting
    if Unit.PDetect > MaxFUPDetect or Unit.Sply < MaxFUSply * MinAccFUSply:
        if Unit.PDetect > MaxFUPDetect:
            PrintLine("EOM for " + FUStr(FUn) + " PDetect high -> FURQO")
        if Unit.Sply < MaxFUSply * MinAccFUSply:
            PrintLine("EOM for " + FUStr(FUn) + " Sply low -> FURQO")
        NewEvent = EventRec(Clock, FURQO, FUn)
    else:
        PrintLine("EOM for " + FUStr(FUn))
        Duration = math.trunc(Random(RNFSeed, 1) * MeanFMInterval)
        Unit.TotalTime[FMWaiting] += Duration
        NewEvent = EventRec(Clock + Duration, FM, FUn)
    Schedule(NewEvent)


def ProcFURQO(CEvnt: EventRec) -> None:
    FUn = CEvnt.UnitID
    if RequirePath(FU[FUn].Dstn).Next is None:
        while True:
            NewLoc = math.trunc(Random(RNFSeed, 0) * MaxNode) + 1
            if NewLoc != FU[FUn].Loc:
                break
        DeletePath(FU[FUn].Dstn)
        FU[FUn].Dstn = RequirePath(ShortestPath(FU[FUn].Loc, NewLoc))
    else:
        FUDstn = RequirePath(FU[FUn].Dstn)
        while FUDstn.Next is not None:
            FUDstn = FUDstn.Next
        NewLoc = FUDstn.NodeID
    OTime = MaxClock
    ONode = OUnit = 0
    OType = "\0"
    Orders = False
    for SUn in range(1, MaxSU + 1):
        if SU[SUn].Allocated:
            continue
        UiTime = MinTime[FU[FUn].Loc][SU[SUn].Loc]
        UfTime = max(MinTime[FU[FUn].Loc][NewLoc], MinTime[SU[SUn].Loc][NewLoc])
        if UiTime <= UfTime and FU[FUn].PDetect < MaxFUPDetect:
            UbNode, UbTime, UbType = FU[FUn].Loc, UiTime, "I"
        else:
            UbNode, UbTime, UbType = NewLoc, UfTime, "F"
        FUDstn = RequirePath(FU[FUn].Dstn)
        PbTime = MaxClock
        PbNode = 0
        while FUDstn.Next is not None:
            if FU[FUn].PDetect > MaxFUPDetect and FUDstn.NodeID == FU[FUn].Loc:
                FUDstn = FUDstn.Next
            else:
                PTime = max(
                    MinTime[FU[FUn].Loc][FUDstn.NodeID],
                    MinTime[SU[SUn].Loc][FUDstn.NodeID],
                )
                if PTime < PbTime:
                    PbNode, PbTime = FUDstn.NodeID, PTime
                FUDstn = FUDstn.Next
        if UbTime * Alpha > PbTime * (1 - Alpha):
            if PbNode == 0:
                raise RuntimeError("No intermediate rendezvous candidate")
            BNode, BTime, BType = PbNode, PbTime, "P"
        else:
            BNode, BTime, BType = UbNode, UbTime, UbType
        if BTime < OTime:
            ONode, OTime, OType, OUnit, Orders = BNode, BTime, BType, SUn, True
    if not Orders:
        SearchEvent = EventQ
        while SearchEvent is not None and SearchEvent.Typ == FURQO:
            SearchEvent = SearchEvent.Next
        if SearchEvent is None:
            raise RuntimeError("Event queue deadlock: no event can release a supply unit")
        NewEvent = EventRec(SearchEvent.Time + 0.000001, FURQO, FUn)
        PrintLine(
            FUStr(FUn) + " Orders> No free SUs!" + " Resch FURQO at " + RealStr(NewEvent.Time)
        )
        Schedule(NewEvent)
        return
    PrintLine(
        FUStr(FUn)
        + " Orders> ReSply Typ:"
        + OType
        + " Node:"
        + IntStr(ONode)
        + " Dstn:"
        + IntStr(NewLoc)
        + " "
        + SUStr(OUnit)
    )
    FU[FUn].ReSplyLoc, FU[FUn].ReSplySU, FU[FUn].ReSplyTyp = ONode, OUnit, OType
    SU[OUnit].ReSplyLoc, SU[OUnit].ReSplyFU, SU[OUnit].Allocated = ONode, FUn, True
    if FU[FUn].Loc == ONode and SU[OUnit].Loc == ONode:
        Schedule(EventRec(Clock, SRS, FUn))
    if FU[FUn].Loc != ONode and SU[OUnit].Loc == ONode:
        SU[OUnit].SplyWaitClock = Clock
        SU[OUnit].Status = SplyWaiting
        PrintLine(SUStr(OUnit) + " waiting for " + FUStr(FUn))
    if FU[FUn].Loc == ONode and SU[OUnit].Loc != ONode:
        FU[FUn].SplyWaitClock = Clock
        FU[FUn].Status = SplyWaiting
        PrintLine(FUStr(FUn) + " waiting for " + SUStr(OUnit))
    if FU[FUn].Loc != ONode:
        Schedule(EventRec(Clock, FUDN, FUn))
    if SU[OUnit].Loc != ONode:
        DeletePath(SU[OUnit].Dstn)
        SU[OUnit].Dstn = RequirePath(ShortestPath(SU[OUnit].Loc, ONode))
        Schedule(EventRec(Clock, SUDN, OUnit))


def ProcFUDN(CurEvent: EventRec) -> None:
    FUn = CurEvent.UnitID
    Unit = FU[FUn]
    NewLoc = RequirePath(RequirePath(Unit.Dstn).Next).NodeID
    Unit.Status = Moving
    Unit.PDetect = 0.0
    NewEvent = EventRec(Clock + MinTime[Unit.Loc][NewLoc] / MaxFUSpeed, FUAN, FUn)
    PrintLine(
        FUStr(FUn) + " depart for Node:" + IntStr(NewLoc) + " Arrive:" + RealStr(NewEvent.Time)
    )
    Unit.TotalTime[Moving] += NewEvent.Time - Clock
    Schedule(NewEvent)


def ProcSUDN(CurEvent: EventRec) -> None:
    SUn = CurEvent.UnitID
    Unit = SU[SUn]
    NewLoc = RequirePath(RequirePath(Unit.Dstn).Next).NodeID
    Unit.Status = Moving
    NewEvent = EventRec(Clock + MinTime[Unit.Loc][NewLoc] / MaxSUSpeed, SUAN, SUn)
    PrintLine(
        SUStr(SUn) + " depart for Node:" + IntStr(NewLoc) + " Arrive:" + RealStr(NewEvent.Time)
    )
    Unit.TotalTime[Moving] += NewEvent.Time - Clock
    Schedule(NewEvent)


def ProcFUAN(CurEvent: EventRec) -> None:
    FUn = CurEvent.UnitID
    Unit = FU[FUn]
    OldPath = RequirePath(Unit.Dstn)
    Unit.Dstn = RequirePath(OldPath.Next)
    Unit.Dstn.Prev = None
    OldPath.Next = None
    NewLoc = Unit.Dstn.NodeID
    Unit.Loc = NewLoc
    if Unit.ReSplySU != 0:
        if Unit.Loc == Unit.ReSplyLoc and SU[Unit.ReSplySU].Loc == Unit.Loc:
            Schedule(EventRec(Clock, SRS, FUn))
        if Unit.Loc == Unit.ReSplyLoc and SU[Unit.ReSplySU].Loc != Unit.Loc:
            Unit.SplyWaitClock = Clock
            Unit.Status = SplyWaiting
            PrintLine(FUStr(FUn) + " waiting for " + SUStr(Unit.ReSplySU))
    if Unit.Loc != Unit.ReSplyLoc and Unit.Dstn.Next is not None:
        Schedule(EventRec(Clock, FUDN, FUn))
    if Unit.Loc != Unit.ReSplyLoc and Unit.Dstn.Next is None:
        Duration = math.trunc(Random(RNFSeed, 1) * MeanFMInterval)
        Schedule(EventRec(Clock + Duration, FM, FUn))


def ProcSUAN(CurEvent: EventRec) -> None:
    SUn = CurEvent.UnitID
    Unit = SU[SUn]
    OldPath = RequirePath(Unit.Dstn)
    Unit.Dstn = RequirePath(OldPath.Next)
    Unit.Dstn.Prev = None
    OldPath.Next = None
    NewLoc = Unit.Dstn.NodeID
    Unit.Loc = NewLoc
    if Unit.Loc == Unit.ReSplyLoc and FU[Unit.ReSplyFU].Loc == Unit.Loc:
        Schedule(EventRec(Clock, SRS, Unit.ReSplyFU))
    if Unit.Loc == Unit.ReSplyLoc and FU[Unit.ReSplyFU].Loc != Unit.Loc:
        Unit.SplyWaitClock = Clock
        Unit.Status = SplyWaiting
        PrintLine(SUStr(SUn) + " waiting for " + FUStr(Unit.ReSplyFU))
    if Unit.Loc != Unit.ReSplyLoc and Unit.Dstn.Next is not None:
        Schedule(EventRec(Clock, SUDN, SUn))


def ProcSRS(CurEvent: EventRec) -> None:
    FUn = CurEvent.UnitID
    SUn = FU[FUn].ReSplySU
    ReSplyTyp = FU[FUn].ReSplyTyp
    if ReSplyTyp in ("I", "F"):
        StatusTyp, Rate = URSupplying, UnitResplyRate
    elif ReSplyTyp == "P":
        StatusTyp, Rate = PRSupplying, PointResplyRate
    else:
        raise RuntimeError(f"Invalid resupply type: {ReSplyTyp!r}")
    Duration = (MaxFUSply - FU[FUn].Sply) / Rate
    for Unit in (FU[FUn], SU[SUn]):
        if Unit.Status == SplyWaiting:
            Unit.TotalTime[SplyWaiting] += Clock - Unit.SplyWaitClock
        Unit.TotalTime[StatusTyp] += Duration
        Unit.Status = StatusTyp
    SU[SUn].NumSM += 1
    PrintLine(FUStr(FUn) + " and " + SUStr(SUn) + " linked." + " -> Begin Resupply")
    Schedule(EventRec(Clock + Duration, ERS, FUn))


def ProcERS(CurEvent: EventRec) -> None:
    global Gap, Issued
    FUn = CurEvent.UnitID
    SUn = FU[FUn].ReSplySU
    PrintLine(FUStr(FUn) + " and " + SUStr(SUn) + " -> END Resupply")
    SU[SUn].ReSplyLoc = SU[SUn].ReSplyFU = 0
    Gap = MaxFUSply - FU[FUn].Sply
    if Gap > SU[SUn].Sply:
        Issued = SU[SUn].Sply
        SU[SUn].Sply = 0
    else:
        Issued = Gap
        SU[SUn].Sply -= Gap
    if SU[SUn].Sply < MaxSUSply * MinAccSUSply:
        Schedule(EventRec(Clock, SATP, SUn))
    else:
        SU[SUn].Allocated = False
        SU[SUn].Status = SplyWaiting
    Unit = FU[FUn]
    Unit.ReSplyLoc = Unit.ReSplySU = 0
    Unit.ReSplyTyp = "\0"
    Unit.Status = FMWaiting
    Unit.Sply = Unit.Sply + Issued if Gap > Issued else MaxFUSply
    if RequirePath(Unit.Dstn).Next is not None:
        Schedule(EventRec(Clock, FUDN, FUn))
    else:
        Duration = math.trunc(Random(RNFSeed, 1) * MeanFMInterval)
        Schedule(EventRec(Clock + Duration, FM, FUn))


def ProcSATP(CurEvent: EventRec) -> None:
    SUn = CurEvent.UnitID
    NewEvent = EventRec(Clock + MinTime[SU[SUn].Loc][ATPNode] / MaxSUSpeed, EATP, SUn)
    PrintLine(SUStr(SUn) + " sply low.  Going to ATP! Arrive:" + RealStr(NewEvent.Time))
    Schedule(NewEvent)
    AtATP.add(SUn)


def ProcEATP(CurEvent: EventRec) -> None:
    SUn = CurEvent.UnitID
    Unit = SU[SUn]
    Unit.Allocated = False
    Unit.Status = SplyWaiting
    Unit.Sply = MaxSUSply
    Unit.Loc = ATPNode
    DeletePath(Unit.Dstn)
    Unit.Dstn = PathRec(Unit.Loc)
    Unit.ReSplyLoc = Unit.ReSplyFU = 0
    AtATP.discard(SUn)
    PrintLine(SUStr(SUn) + " resupplied at ATP SU now available")


def HandleEvents() -> None:
    global EventQ, Clock
    if EventQ is None:
        Clock = MaxClock
        return
    CurEvent = EventQ
    EventQ = CurEvent.Next
    CurEvent.Next = None
    Clock = CurEvent.Time
    Handlers = {
        FM: ProcFM,
        EOM: ProcEOM,
        FURQO: ProcFURQO,
        FUDN: ProcFUDN,
        SUDN: ProcSUDN,
        FUAN: ProcFUAN,
        SUAN: ProcSUAN,
        SRS: ProcSRS,
        ERS: ProcERS,
        SATP: ProcSATP,
        EATP: ProcEATP,
    }
    Handlers[CurEvent.Typ](CurEvent)


def PrintStatistics() -> None:
    if DataFile is None:
        return
    for FUn in range(1, MaxFU + 1):
        DataFile.write(f"FU: {FUn}\n")
        for StatusTime in UnitStatusType:
            DataFile.write(f"{StatusTime.name}: {FU[FUn].TotalTime[StatusTime]:10.2f}\n")
        DataFile.write(f"Number of Fire Missions: {FU[FUn].NumFM}\n")
    for SUn in range(1, MaxSU + 1):
        DataFile.write(f"SU: {SUn}\n")
        for StatusTime in UnitStatusType:
            DataFile.write(f"{StatusTime.name}: {SU[SUn].TotalTime[StatusTime]:10.2f}\n")
        DataFile.write(f"Total FU Resupply Missions: {SU[SUn].NumSM}\n")
    DataFile.write(f"Total Number of Rounds Fired: {TotalRounds}\n")


def InitModel(Seed: int = 5) -> None:
    global Clock, TotalRounds, Gap, Issued, Complete, Paused
    if not 1 <= Seed < 2147483647:
        raise ValueError("Seed must be in 1..2147483646")
    RNFSeed.Value = Seed
    for Unit in (*FU.values(), *SU.values()):
        DeletePath(Unit.Dstn)
    Node.clear()
    LastLines.clear()
    AtATP.clear()
    Clock = 0.0
    TotalRounds = Gap = Issued = 0
    Complete = Paused = False
    InitNodeAry()
    InitArcAry()
    InitConnAry()
    InitTravelTimeAry()
    ConnNodes()
    InitMinTimeAry()
    InitFUAry()
    InitSUAry()
    InitEventQ()


def StepModel() -> None:
    global Complete
    if Complete:
        return
    HandleEvents()
    Complete = Clock > MaxClock or EventQ is None


def InitHardware() -> None:
    global pygame, Screen
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame as Pygame

    pygame = Pygame
    pygame.display.init()
    pygame.font.init()
    Screen = pygame.display.set_mode((1280, 960), pygame.RESIZABLE)
    pygame.display.set_caption("FASIM III - Field Artillery Simulator")
    SetScale(2.0)


def SetScale(NewScale: float) -> None:
    """Size fonts for the current window scale (logical layout is 640x480)."""
    global Scale, Font, SmallFont
    Scale = NewScale
    Font = pygame.font.Font(None, max(8, round(16 * Scale)))
    SmallFont = pygame.font.Font(None, max(8, round(13 * Scale)))


def P(X: float, Y: float) -> tuple[int, int]:
    """Map a logical 640x480 point to window pixels."""
    return (round(X * Scale) + OffsetX, round(Y * Scale) + OffsetY)


def L(V: float) -> int:
    """Map a logical length to window pixels (never less than 1)."""
    return max(1, round(V * Scale))


def DrawText(TextFont, Text: str, Color, X: float, Y: float) -> None:
    Canvas.blit(TextFont.render(Text, True, Color), P(X, Y))


def DrawFireUnit(X: int, Y: int, FUn: int) -> None:
    pygame.draw.rect(Canvas, DefFUClr, (*P(X - 5, Y + 2), L(11), L(2)))
    for Offset in (-1, -2, -3):
        pygame.draw.line(Canvas, DefFUClr, P(X + Offset, Y - 3), P(X + Offset + 4, Y + 1), L(1))
    DrawText(SmallFont, str(FUn), DefFUClr, X - 3, Y + 5)


def DrawSplyUnit(X: int, Y: int, SUn: int) -> None:
    pygame.draw.rect(Canvas, DefSUClr, (*P(X - 3, Y - 2), L(7), L(4)))
    pygame.draw.rect(Canvas, DefSUClr, (*P(X - 4, Y + 2), L(2), L(2)))
    pygame.draw.rect(Canvas, DefSUClr, (*P(X + 3, Y + 2), L(2), L(2)))
    DrawText(SmallFont, str(SUn), DefSUClr, X - 3, Y + 5)


def DrawFireUnits() -> None:
    for FUn in range(1, MaxFU + 1):
        Unit = FU[FUn]
        X, Y = Node[Unit.Loc].X, Node[Unit.Loc].Y
        if Unit.Status == Moving and Unit.Dstn is not None and Unit.Dstn.Next is not None:
            NewLoc = Unit.Dstn.Next.NodeID
            X = round((X + Node[NewLoc].X) / 2)
            Y = round((Y + Node[NewLoc].Y) / 2)
        DrawFireUnit(X - 4, Y, FUn)


def DrawSplyUnits() -> None:
    for SUn in range(1, MaxSU + 1):
        if SUn in AtATP:
            continue
        Unit = SU[SUn]
        X, Y = Node[Unit.Loc].X, Node[Unit.Loc].Y
        if Unit.Status == Moving and Unit.Dstn is not None and Unit.Dstn.Next is not None:
            NewLoc = Unit.Dstn.Next.NodeID
            X = round((X + Node[NewLoc].X) / 2)
            Y = round((Y + Node[NewLoc].Y) / 2)
        DrawSplyUnit(X + 5, Y, SUn)


def DrawMap() -> None:
    global Canvas, OffsetX, OffsetY
    Width, Height = Screen.get_size()
    NewScale = max(0.25, min(Width / 640, Height / 480))
    if abs(NewScale - Scale) > 1e-6:
        SetScale(NewScale)
    OffsetX = (Width - round(640 * Scale)) // 2
    OffsetY = (Height - round(480 * Scale)) // 2
    Canvas = Screen
    Canvas.fill((0, 0, 0))
    for SNode in range(1, MaxNode + 1):
        for ENode in range(SNode + 1, MaxNode + 1):
            if Conn[SNode][ENode]:
                pygame.draw.aaline(
                    Canvas,
                    DefArcClr,
                    P(Node[SNode].X, Node[SNode].Y),
                    P(Node[ENode].X, Node[ENode].Y),
                )
    for SNode in range(1, MaxNode + 1):
        X, Y = Node[SNode].X, Node[SNode].Y
        pygame.draw.circle(Canvas, DefNodeClr, P(X, Y), L(10), L(1))
        Label = Font.render(IntStr(SNode), True, DefNodeClr)
        LX, LY = P(X, Y - 23)
        Canvas.blit(Label, (LX - Label.get_width() // 2, LY))
    DrawFireUnits()
    DrawSplyUnits()
    pygame.draw.rect(Canvas, (0, 0, 0), (*P(0, 0), L(640), L(16)))
    State = "COMPLETE" if Complete else "PAUSED" if Paused else "RUNNING"
    DrawText(
        Font,
        f"Clock: {Clock:.4f} / {MaxClock:g}    Rounds: {TotalRounds}    {State}",
        DefTextClr,
        5,
        2,
    )
    pygame.draw.rect(Canvas, (14, 20, 31), (*P(0, 351), L(640), L(129)))
    DrawText(Font, "FASIM III", DefHiLiteClr, 8, 357)
    LegendX = 95
    for Text, Color in (
        (f"Yellow: fire units ({MaxFU} total)", DefFUClr),
        (f"Green: supply units ({MaxSU} total)", DefSUClr),
        (f"Ammo Transfer Point: Node {ATPNode}", DefTextClr),
    ):
        Label = Font.render(Text, True, Color)
        Canvas.blit(Label, P(LegendX, 357))
        LegendX += Label.get_width() / Scale + 16
    for I, Line in enumerate(LastLines):
        DrawText(SmallFont, Line, DefTextClr, 8, 377 + I * 14)
    DrawText(
        Font,
        f"Space: pause    N: step    +/-: speed ({EventsPerSecond:g} events/s)    Esc: close",
        DefHiLiteClr,
        8,
        439,
    )
    Footer = (
        "Complete - SimRun.Doc saved. Close the window to exit."
        if Complete
        else "SimRun.Doc: event log and unit statistics"
    )
    DrawText(SmallFont, Footer, (165, 180, 200), 8, 460)
    pygame.display.flip()


def SaveStatistics() -> None:
    global DataFile
    if DataFile is not None:
        PrintStatistics()
        DataFile.close()
        DataFile = None


def RunGraphics(ExitOnComplete: bool = False) -> None:
    global Paused, EventsPerSecond
    InitHardware()
    FrameClock = pygame.time.Clock()
    Accumulator = 0.0
    Running = True
    while Running:
        Elapsed = min(FrameClock.tick(60) / 1000.0, 0.25)
        for InputEvent in pygame.event.get():
            if InputEvent.type == pygame.QUIT:
                Running = False
            elif InputEvent.type == pygame.KEYDOWN:
                if InputEvent.key == pygame.K_ESCAPE:
                    Running = False
                elif InputEvent.key == pygame.K_SPACE:
                    Paused = not Paused
                    Accumulator = 0.0
                elif InputEvent.key in (pygame.K_n, pygame.K_RIGHT):
                    Paused = True
                    Accumulator = 0.0
                    StepModel()
                elif InputEvent.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    EventsPerSecond = min(EventsPerSecond * 2, 1000)
                elif InputEvent.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    EventsPerSecond = max(EventsPerSecond / 2, 1)
        if not Running:
            break
        if not Paused and not Complete:
            Accumulator += Elapsed * EventsPerSecond
            while Accumulator >= 1 and not Complete:
                StepModel()
                Accumulator -= 1
        if Complete:
            SaveStatistics()
        DrawMap()
        if Complete and ExitOnComplete:
            Running = False


def main(argv: list[str] | None = None) -> int:
    global MaxClock, DataFile, EventsPerSecond
    Parser = argparse.ArgumentParser(description=__doc__)
    Parser.add_argument("--headless", action="store_true", help="Run without graphics")
    Parser.add_argument("--seed", type=int, default=5, help="Park-Miller initial seed (default: 5)")
    Parser.add_argument(
        "--max-clock", type=float, default=1000, help="Simulation horizon (default: 1000)"
    )
    Parser.add_argument(
        "--events-per-second", type=float, default=25, help="Display playback rate, 1..1000"
    )
    Parser.add_argument("--output", type=FilePath, default=FilePath("SimRun.Doc"))
    Parser.add_argument(
        "--exit-on-complete", action="store_true", help="Close graphics when the run completes"
    )
    Args = Parser.parse_args(argv)
    if not 1 <= Args.seed < 2147483647:
        Parser.error("--seed must be in 1..2147483646")
    if not math.isfinite(Args.max_clock) or Args.max_clock < 0:
        Parser.error("--max-clock must be finite and nonnegative")
    if not 1 <= Args.events_per_second <= 1000:
        Parser.error("--events-per-second must be in 1..1000")
    MaxClock = Args.max_clock
    EventsPerSecond = Args.events_per_second
    try:
        InitModel(Args.seed)
        DataFile = Args.output.open("w", encoding="ascii", newline="\r\n")
        if Args.headless:
            while not Complete:
                StepModel()
        else:
            RunGraphics(Args.exit_on_complete)
        SaveStatistics()
        State = "Completed" if Complete else "Stopped early"
        print(
            f"{State} at clock {Clock:.4f}; {TotalRounds} rounds. Report: {Args.output.resolve()}"
        )
        return 0
    except (OSError, RuntimeError, ValueError) as Error:
        print(f"FASIM3: {Error}", file=sys.stderr)
        return 1
    finally:
        if DataFile is not None:
            DataFile.close()
            DataFile = None
        if pygame is not None:
            pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
