from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ContainerType(Base):
    __tablename__ = "container_types"

    prefix = Column(String, primary_key=True)          # e.g. "CB" — chosen by the human at registration time
    name = Column(String, nullable=False)               # e.g. "clear plastic bucket, ~1 cu ft"
    default_child_count = Column(Integer, nullable=True)  # e.g. 20 for a Harbor Freight 20-bin case — lets registering one instance auto-stage its known sub-bins
    label_tier = Column(String, nullable=False, default="outer")  # "outer" (landscape strip + ArUco marker), "inner_40x30" (HF-style sub-bin, text-only), "inner_20x10" (printed Sortimo box, text-only), "none" (never physically labeled — ITM/ITMN lookup records)
    numbering_scope = Column(String, nullable=False, default="parent")  # "parent" (code = parent_code-NN, permanently tied to whichever parent it was created under — HF sub-bins) or "global" (code = type_prefix-NNN, independent of current parent — reshuffleable printed boxes; parent_code becomes a pure "current location" pointer, changeable via /containers/{code}/move without ever touching the code)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Container(Base):
    __tablename__ = "containers"

    code = Column(String, primary_key=True)             # e.g. "CB-01" or, nested, "AA-01-02"
    type_prefix = Column(String, ForeignKey("container_types.prefix"), nullable=False)
    parent_code = Column(String, ForeignKey("containers.code"), nullable=True)
    sequence = Column(Integer, nullable=False)           # the numeric suffix, scoped to (type_prefix, parent_code)
    domain = Column(String, nullable=False, default="general")  # e.g. "honda-cb550" — keeps earmarked stock separate from general stock even when the physical part is identical
    aruco_id = Column(Integer, nullable=True, unique=True)  # marker ID within DICT_5X5_250 (0-249); only outer-tier containers get one, see label-maker service
    locator = Column(String, nullable=True)  # free-text, this INSTANCE only — e.g. "Mounted above reloading workbench", "Halloween crafts". Not a printed label (see label-maker) — just a human-readable note distinguishing one instance from siblings of the same type.
    ai_description = Column(String, nullable=True)  # vision-identify's raw output (name + text_on_package) for this container's reference photo, stored as-is. Search fodder, not human-facing truth — locator wins when both exist (see registration's _container_search_dict / display logic).
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
