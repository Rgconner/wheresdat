"""Seed (and sync) the wheresdat KanBanMan board's permanent Menu cards.

Safe to re-run — existing cards get their pinned/order/target synced to
match MENU_TREE below rather than just being skipped, so editing this
file and re-running is how you change the menu going forward (e.g. the
"New container type" pin/order flip on 2026-09-07, see below). Task-
column cards (Register, Return, Rescan, Reorder, Remind) are NOT seeded
here; those populate themselves from real events (see registration/
main.py's _notify_register_card for the first one).

Two-level tree: "Register" is a parent card (no target of its own) whose
children are the actual registration actions. Kept to 2 levels per
KanBanMan's "no more than 3 clicks, 2 preferred" budget — see
kanbanman/DESIGN.md's drill-down section.

"New container type" is pinned and listed first, not buried unpinned —
first pass assumed defining a new type would be rare, but for a project
that's mostly cataloging one-off/varied containers, it's often the
necessary first step before "Register a case" even has something to
select (you can't register an instance of a type that doesn't exist
yet). Corrected after Russ's own QA: "A new empty case is the most
likely thing I am doing."

Usage: KANBAN_URL=http://localhost:8300 python scripts/seed_kanban.py
"""

import os

import httpx

KANBAN_URL = os.getenv("KANBAN_URL", "http://localhost:8300")
BOARD = "wheresdat"

# target is a full URL for a separate service; a "#anchor" tag for
# something not built yet as its own page (registration's onNavigate
# only maps a handful of anchors to real form panels — anything else
# falls through to a generic "Not built yet" explanation panel).
MENU_TREE = [
    {"title": "Register", "children": [
        {"title": "New container type", "target": "#register-type", "pinned": True, "order": 0},
        {"title": "Register a case (+ sub-bins)", "target": "#register-case", "pinned": True, "order": 1},
        {"title": "Stage containers", "target": "#stage-containers", "pinned": True, "order": 2},
        {"title": "Move a container", "target": "#move-container", "pinned": True, "order": 3},
        {"title": "Set locator", "target": "#set-locator", "pinned": True, "order": 4},
        {"title": "Attach photo", "target": "#attach-photo", "pinned": True, "order": 5},
    ]},
    {"title": "Find a container", "target": "#find-container"},
    {"title": "Find by photo", "target": "#find-by-photo"},
    {"title": "Print Labels", "target": "http://192.0.2.15:8103/docs"},
    {"title": "LOG ORDER", "target": "#log-order"},
]


def _existing_by_title(client, parent_id=None):
    params = {"column": "Menu", "card_type": "menu"}
    cards = client.get(f"{KANBAN_URL}/boards/{BOARD}/cards", params=params).json()
    return {c["title"]: c for c in cards if c.get("parent_id") == parent_id}


def _create(client, title, target=None, parent_id=None, pinned=True, order=0):
    resp = client.post(
        f"{KANBAN_URL}/boards/{BOARD}/cards",
        json={
            "column": "Menu",
            "title": title,
            "card_type": "menu",
            "pinned": pinned,
            "order": order,
            "target": target,
            "parent_id": parent_id,
        },
    )
    resp.raise_for_status()
    return resp.json()


def _sync(client, existing_card, target=None, pinned=True, order=0):
    changes = {}
    if existing_card.get("pinned") != pinned:
        changes["pinned"] = pinned
    if existing_card.get("order") != order:
        changes["order"] = order
    if target is not None and existing_card.get("target") != target:
        changes["target"] = target
    if not changes:
        return False
    resp = client.patch(f"{KANBAN_URL}/cards/{existing_card['id']}", json=changes)
    resp.raise_for_status()
    return True


def main():
    with httpx.Client(timeout=5.0) as client:
        existing_roots = _existing_by_title(client, parent_id=None)

        for node in MENU_TREE:
            if node["title"] in existing_roots:
                card = existing_roots[node["title"]]
                if _sync(client, card, target=node.get("target"), pinned=True, order=node.get("order", 0)):
                    print(f"synced: {node['title']}")
                else:
                    print(f"skip (up to date): {node['title']}")
            else:
                card = _create(client, node["title"], target=node.get("target"), pinned=True, order=node.get("order", 0))
                print(f"created: {node['title']}")

            if "children" in node:
                existing_children = _existing_by_title(client, parent_id=card["id"])
                for child in node["children"]:
                    if child["title"] in existing_children:
                        existing_child = existing_children[child["title"]]
                        if _sync(client, existing_child, target=child["target"], pinned=child["pinned"], order=child["order"]):
                            print(f"  synced: {child['title']}")
                        else:
                            print(f"  skip (up to date): {child['title']}")
                        continue
                    _create(client, child["title"], target=child["target"], parent_id=card["id"], pinned=child["pinned"], order=child["order"])
                    print(f"  created: {child['title']}")


if __name__ == "__main__":
    main()
