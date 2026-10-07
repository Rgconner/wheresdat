# WheresDat

A small-parts inventory system built for low-friction use. It answers "where is X?"
and "how much X do I have?" without bookkeeping on every put-away.

Fasteners, springs, washers and other odds and ends pile up faster than anyone
organizes them. WheresDat is designed for the person who just wants to find things,
not maintain a perfect catalog: rough counts (one, a few, many) instead of exact
ones, "what kind of part is this?" accepted as a good enough answer, and asking the
human instead of silently guessing.

## What's in it

| Component | What it does |
|---|---|
| `services/datastore` | Containers, part types and locations (FastAPI + PostgreSQL). Containers belong to a *domain*, so identical parts reserved for different projects stay separate. |
| `services/registration` | The externally exposed API and the desktop and phone UIs for registering containers and parts. |
| `services/label-maker` | Generates container labels and plaques. |
| `pi-print-agent` | Runs on a Raspberry Pi and drives two USB thermal label printers (chosen by label size) over raw ESC/POS. |
| `voice-pi` | Hands-free lookup on a Raspberry Pi: wake word, local speech-to-text (faster-whisper), text-to-speech (Piper), and a local cache so it still answers when the network is down. |
| `hardware` | OpenSCAD sources and STLs for the shelves, trays and Sortimo-compatible boxes. |
| `k8s` | Kubernetes manifests for running the services on a homelab cluster. |

`SPEC.md` is the full design document: personas, goals and non-goals, the capture
station, operating modes, and the build punch list.

## Running locally

```
docker compose up -d --build
```

A second, isolated QA stack can run alongside it:

```
docker compose --env-file .env.qa -p wheresdat-qa up -d --build
```

IP addresses in the configs are placeholders from the documentation range
(192.0.2.x). Replace them with your own hosts. The Kubernetes build also pulls
two shared libraries (a kanban board engine and a common service library) that
are not yet published, so the `kanbanman` service will not build from this repo alone.

## Status

Working proof of concept in daily use: registration, the datastore, label
printing, and voice lookup run today. Vision-based identification and
consolidation suggestions are in progress. See the punch list in `SPEC.md`.

## License

MIT
