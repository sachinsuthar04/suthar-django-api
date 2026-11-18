"""
Kinship engine.

Only three kinds of facts are stored: parent-of (father/mother), married-to
(spouse).  Every relation name ("Kaka", "Bhabhi", "Saala" ...) is COMPUTED from
those facts relative to an "ego" (the logged-in person).  Nothing here writes
to the database.

Public API
    KinshipGraph.from_members(members)
    relation_between(graph, ego_id, target_id) -> Rel
    relations_from(graph, ego_id) -> {member_id: Rel}
    collect_ego_tree(ego, up, down, collateral, include_inlaws, include_household)
"""
from dataclasses import dataclass
from collections import deque
from typing import Dict, Iterable, List, Optional

MALE = "male"
FEMALE = "female"


@dataclass(frozen=True)
class Rel:
    key: str
    label: str


LABELS = {
    "self": "Self",
    "father": "Father", "mother": "Mother", "parent": "Parent",
    "son": "Son", "daughter": "Daughter", "child": "Child",
    "husband": "Husband", "wife": "Wife", "spouse": "Spouse",
    "brother": "Brother", "sister": "Sister", "sibling": "Sibling",
    "grandfather": "Grandfather", "grandmother": "Grandmother", "grandparent": "Grandparent",
    "grandson": "Grandson", "granddaughter": "Granddaughter", "grandchild": "Grandchild",
    "great_grandfather": "Great Grandfather", "great_grandmother": "Great Grandmother",
    "great_grandparent": "Great Grandparent",
    "great_grandson": "Great Grandson", "great_granddaughter": "Great Granddaughter",
    "great_grandchild": "Great Grandchild",
    "ancestor": "Ancestor", "descendant": "Descendant",
    # father's side
    "kaka": "Kaka", "kaki": "Kaki", "bua": "Bua", "fua": "Fua",
    # mother's side
    "mama": "Mama", "mami": "Mami", "masi": "Masi", "masa": "Masa",
    "uncle": "Uncle", "aunt": "Aunt",
    "grand_uncle": "Grand Uncle", "grand_aunt": "Grand Aunt",
    "nephew": "Nephew", "niece": "Niece", "nibling": "Nephew/Niece",
    "grand_nephew": "Grand Nephew", "grand_niece": "Grand Niece",
    "cousin_brother": "Cousin Brother", "cousin_sister": "Cousin Sister", "cousin": "Cousin",
    # via marriage
    "father_in_law": "Father-in-law", "mother_in_law": "Mother-in-law",
    "saala": "Saala", "saali": "Saali", "devar": "Devar", "nanand": "Nanand",
    "bhabhi": "Bhabhi", "jija": "Jija",
    "daughter_in_law": "Daughter-in-law", "son_in_law": "Son-in-law",
    "stepmother": "Stepmother", "stepfather": "Stepfather",
    "stepson": "Stepson", "stepdaughter": "Stepdaughter",
    "in_law": "In-law",
    "relative": "Relative",
}


def rel(key: str) -> Rel:
    return Rel(key, LABELS[key])


def _by_gender(gender: Optional[str], male: str, female: str, neutral: str) -> Rel:
    if gender == MALE:
        return rel(male)
    if gender == FEMALE:
        return rel(female)
    return rel(neutral)


@dataclass
class Person:
    id: int
    gender: Optional[str]
    father_id: Optional[int]
    mother_id: Optional[int]
    spouse_id: Optional[int]


class KinshipGraph:
    def __init__(self, persons: Iterable[Person]):
        self.persons: Dict[int, Person] = {p.id: p for p in persons}
        # make spouse links symmetric even if only one side is stored
        self.spouse: Dict[int, int] = {}
        for p in self.persons.values():
            if p.spouse_id and p.spouse_id in self.persons:
                self.spouse.setdefault(p.id, p.spouse_id)
                self.spouse.setdefault(p.spouse_id, p.id)

    @classmethod
    def from_members(cls, members) -> "KinshipGraph":
        return cls(
            Person(m.id, m.gender, m.father_id, m.mother_id, m.spouse_id) for m in members
        )

    def parents(self, pid: int) -> List[tuple]:
        """[(parent_id, 'father'|'mother')] for parents present in the graph."""
        p = self.persons.get(pid)
        out = []
        if p:
            if p.father_id in self.persons:
                out.append((p.father_id, "father"))
            if p.mother_id in self.persons:
                out.append((p.mother_id, "mother"))
        return out

    def ancestors(self, pid: int) -> Dict[int, tuple]:
        """{ancestor_id: (depth, first_step)}; includes the person at depth 0.
        first_step = 'father'|'mother' = which parent of `pid` the line passes."""
        result: Dict[int, tuple] = {pid: (0, None)}
        queue = deque([pid])
        while queue:
            cur = queue.popleft()
            depth, first = result[cur]
            for parent_id, slot in self.parents(cur):
                if parent_id in result:
                    continue
                result[parent_id] = (depth + 1, first or slot)
                queue.append(parent_id)
        return result

    def gender_of(self, pid: int, ego_id: Optional[int] = None) -> Optional[str]:
        p = self.persons[pid]
        if p.gender in (MALE, FEMALE):
            return p.gender
        # infer from the parent slot if gender unknown
        for child in self.persons.values():
            if child.father_id == pid:
                return MALE
            if child.mother_id == pid:
                return FEMALE
        return None


# ---------------------------------------------------------------------------
# blood relation
# ---------------------------------------------------------------------------
def _blood(graph: KinshipGraph, ego_id: int, target_id: int) -> Optional[Rel]:
    if ego_id == target_id:
        return rel("self")

    anc_ego = graph.ancestors(ego_id)
    anc_tgt = graph.ancestors(target_id)
    common = set(anc_ego) & set(anc_tgt)
    if not common:
        return None

    best = min(common, key=lambda a: (anc_ego[a][0] + anc_tgt[a][0], anc_ego[a][0]))
    u, side = anc_ego[best]
    d = anc_tgt[best][0]
    g = graph.gender_of(target_id)

    if d == 0:  # target is an ancestor of ego
        if u == 1:
            return _by_gender(g, "father", "mother", "parent")
        if u == 2:
            return _by_gender(g, "grandfather", "grandmother", "grandparent")
        if u == 3:
            return _by_gender(g, "great_grandfather", "great_grandmother", "great_grandparent")
        return rel("ancestor")

    if u == 0:  # target is a descendant of ego
        if d == 1:
            return _by_gender(g, "son", "daughter", "child")
        if d == 2:
            return _by_gender(g, "grandson", "granddaughter", "grandchild")
        if d == 3:
            return _by_gender(g, "great_grandson", "great_granddaughter", "great_grandchild")
        return rel("descendant")

    if u == 1 and d == 1:
        return _by_gender(g, "brother", "sister", "sibling")
    if u == 2 and d == 1:  # parent's sibling
        if side == "father":
            return _by_gender(g, "kaka", "bua", "uncle")
        return _by_gender(g, "mama", "masi", "aunt")
    if u == 1 and d == 2:
        return _by_gender(g, "nephew", "niece", "nibling")
    if u == 2 and d == 2:
        return _by_gender(g, "cousin_brother", "cousin_sister", "cousin")
    if u == 3 and d == 1:
        return _by_gender(g, "grand_uncle", "grand_aunt", "relative")
    if u == 1 and d == 3:
        return _by_gender(g, "grand_nephew", "grand_niece", "relative")
    return rel("relative")


# target is the SPOUSE of ego's blood relative X (key of X -> key of target)
_SPOUSE_OF_BLOOD = {
    "brother": "bhabhi",
    "sister": "jija",
    "son": "daughter_in_law",
    "daughter": "son_in_law",
    "kaka": "kaki",
    "bua": "fua",
    "mama": "mami",
    "masi": "masa",
    "uncle": "aunt",
    "aunt": "uncle",
    "grandfather": "grandmother",
    "grandmother": "grandfather",
}


def relation_between(graph: KinshipGraph, ego_id: int, target_id: int) -> Rel:
    """Relation of `target` relative to `ego` ("target is ego's ...")."""
    if ego_id not in graph.persons or target_id not in graph.persons:
        return rel("relative")
    if ego_id == target_id:
        return rel("self")

    # 1. direct spouse
    if graph.spouse.get(ego_id) == target_id:
        return _by_gender(graph.gender_of(target_id), "husband", "wife", "spouse")

    # 2. blood
    r = _blood(graph, ego_id, target_id)
    if r:
        return r

    # 3. target is a blood relative of ego's spouse -> in-laws
    ego_spouse = graph.spouse.get(ego_id)
    if ego_spouse:
        r = _blood(graph, ego_spouse, target_id)
        if r:
            ego_g = graph.gender_of(ego_id)
            if r.key == "father":
                return rel("father_in_law")
            if r.key == "mother":
                return rel("mother_in_law")
            if r.key == "brother":
                return rel("saala") if ego_g == MALE else rel("devar")
            if r.key == "sister":
                return rel("saali") if ego_g == MALE else rel("nanand")
            if r.key in ("son", "daughter", "child"):
                return _by_gender(graph.gender_of(target_id), "stepson", "stepdaughter", "in_law")
            return rel("in_law")

    # 4. target is the spouse of a blood relative of ego
    target_spouse = graph.spouse.get(target_id)
    if target_spouse:
        r = _blood(graph, ego_id, target_spouse)
        if r:
            if r.key == "father":
                return rel("stepmother")
            if r.key == "mother":
                return rel("stepfather")
            mapped = _SPOUSE_OF_BLOOD.get(r.key)
            return rel(mapped) if mapped else rel("in_law")

    return rel("relative")


def relations_from(graph: KinshipGraph, ego_id: int) -> Dict[int, Rel]:
    return {pid: relation_between(graph, ego_id, pid) for pid in graph.persons}


# ---------------------------------------------------------------------------
# ego tree loader (read only, a few queries per generation - never per node)
# ---------------------------------------------------------------------------
def collect_ego_tree(
    ego,
    up: int = 3,
    down: int = 3,
    collateral: int = 2,
    include_inlaws: bool = True,
    include_household: bool = True,
    include_maternal: bool = True,
):
    """
    Hourglass around `ego`:
      * ancestors up to `up` generations
      * ego's own descendants down to `down` generations
      * descendants of every ancestor (siblings, nephews, uncles, cousins) down
        to `collateral` generations (1 above the great-grandparents)
      * spouse of everyone selected
      * (include_inlaws) the ego's spouse's parents and siblings
      * (include_household) everyone in ego's household, even if not linked yet
    Returns {member_id: Member}.
    """
    from django.db.models import Q
    from members.models import Member

    up = max(0, min(int(up), 6))
    down = max(0, min(int(down), 6))
    collateral = max(0, min(int(collateral), 3))

    selected: Dict[int, "Member"] = {ego.id: ego}

    def fetch(qs):
        new = []
        for m in qs:
            if m.id not in selected:
                selected[m.id] = m
                new.append(m)
        return new

    base = Member.objects.select_related("user__user_profile__personal", "family")

    # --- ancestors by generation
    levels = {0: [ego]}
    current = [ego]
    for k in range(1, up + 1):
        if not include_maternal:
            # "Both sides" switched off: do not climb the mother's line
            current = [m for m in current if not (k >= 2 and m.id == ego.mother_id)]
        ids = set()
        for m in current:
            ids.update(i for i in (m.father_id, m.mother_id) if i)
        ids -= set(selected)
        if not ids:
            # parents may already be selected through another path
            current = [selected[i] for m in current for i in (m.father_id, m.mother_id) if i in selected]
            levels[k] = current
            if not current:
                break
            continue
        fetch(base.filter(id__in=ids))
        current = [selected[i] for i in {j for m in current for j in (m.father_id, m.mother_id) if j} if i in selected]
        levels[k] = current

    def add_descendants(roots, depth):
        frontier = list(roots)
        for _ in range(depth):
            ids = [m.id for m in frontier]
            if not ids:
                break
            frontier = fetch(base.filter(Q(father_id__in=ids) | Q(mother_id__in=ids)))

    add_descendants([ego], down)
    if collateral:
        for k, members in levels.items():
            if k >= 1:
                add_descendants(members, collateral if k <= 2 else 1)

    # --- in-laws: ego's spouse's parents + siblings
    if include_inlaws:
        spouse = selected.get(ego.spouse_id) if ego.spouse_id else None
        if ego.spouse_id and spouse is None:
            fetch(base.filter(id=ego.spouse_id))
            spouse = selected.get(ego.spouse_id)
        if spouse:
            parent_ids = [i for i in (spouse.father_id, spouse.mother_id) if i]
            if parent_ids:
                parents = fetch(base.filter(id__in=parent_ids))
                add_descendants([selected[i] for i in parent_ids if i in selected] or parents, 1)

    # --- spouses of everyone selected
    spouse_ids = {m.spouse_id for m in selected.values() if m.spouse_id} - set(selected)
    if spouse_ids:
        fetch(base.filter(id__in=spouse_ids))
    # spouse stored only on the other side
    ids = list(selected)
    fetch(base.filter(spouse_id__in=ids))

    if include_household and ego.family_id:
        fetch(base.filter(family_id=ego.family_id))

    return selected


def build_edges(members: Dict[int, "object"]) -> List[dict]:
    edges = set()
    for m in members.values():
        if m.spouse_id and m.spouse_id in members:
            a, b = sorted((m.id, m.spouse_id))
            edges.add((a, b, "spouse"))
        if m.father_id and m.father_id in members:
            edges.add((m.father_id, m.id, "father"))
        if m.mother_id and m.mother_id in members:
            edges.add((m.mother_id, m.id, "mother"))
    return [{"source": s, "target": t, "type": k} for s, t, k in sorted(edges)]


def generation_span(members: Dict[int, "object"], ego_id: int) -> int:
    """How many generations the tree shows (grandparents .. grandchildren = 5).
    Parents are one level up, children one level down, spouses the same level."""
    level = {ego_id: 0}
    queue = deque([ego_id])
    children_of: Dict[int, List[int]] = {}
    for m in members.values():
        for pid in (m.father_id, m.mother_id):
            if pid:
                children_of.setdefault(pid, []).append(m.id)
    while queue:
        cur = queue.popleft()
        m = members.get(cur)
        if m is None:
            continue
        neighbours = []
        if m.father_id in members:
            neighbours.append((m.father_id, -1))
        if m.mother_id in members:
            neighbours.append((m.mother_id, -1))
        if m.spouse_id in members:
            neighbours.append((m.spouse_id, 0))
        neighbours += [(cid, 1) for cid in children_of.get(cur, [])]
        for nid, delta in neighbours:
            if nid not in level:
                level[nid] = level[cur] + delta
                queue.append(nid)
    return (max(level.values()) - min(level.values()) + 1) if level else 1
