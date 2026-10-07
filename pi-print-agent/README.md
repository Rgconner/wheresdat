# WheresDat pi-print-agent

Linux port of `scripts/print_agent.py` (the Windows print agent),
running on the same Pi as `voice-pi` — see that directory's README for
why a dedicated Pi at all. This one exists to get printing off the
Windows workstation entirely: the Windows agent needed an NSSM service
tied to that specific machine being powered on, which meant it couldn't
sleep. This Pi is already always-on for voice retrieval; printing just
rides along.

**Same HTTP contract as the Windows agent, on purpose.** The
registration UI (`services/registration/static/index.html`,
`phone.html`) talks to whatever `PRINT_AGENT_URL` is configured to —
pointing it at this Pi instead of the Windows workstation is a config
change, not a UI code change.

## Why simpler than the Windows version

The Windows agent has to fight the OS's GDI print-queue machinery (see
`scripts/print_label.py`'s docstring for the full saga — a broken
driver, three failed DEVMODE strategies, eventually a hand-built raw
ESC/POS byte stream sent through the print queue's RAW passthrough).

On Linux, confirmed live via `dmesg`, the M110S enumerates as a genuine
USB Printer Class device (`proto 2`, bidirectional) — the kernel's
built-in `usblp` driver picks it up automatically and exposes it as
`/dev/usb/lp0`. No custom driver, no `pyusb`, no `pyserial`. Printing
is the *same* raw ESC/POS bytes as the Windows version, just written
straight to that device file.

One real gotcha, confirmed live: a plain `file.write(payload)` on that
device silently short-wrote — of a ~1620-byte payload, only the last
couple characters' worth actually reached the printer, with no error
raised. Character devices don't give the same "the whole buffer went
out" guarantee a normal file write does. `print_label.py`'s
`_write_all()` loops on `os.write()`'s actual return value to fix this
— don't revert to a plain `.write()` call even though it looks
equivalent and mostly seems to work on small payloads.

## Setup

```bash
scp -r pi-print-agent/ rgcon@<pi-hostname>:/home/rgcon/wheresdat-print
ssh rgcon@<pi-hostname>
cd /home/rgcon/wheresdat-print
./install-service.sh
```

`install-service.sh` adds `rgcon` to the `lp` group if it isn't already
(needed to write `/dev/usb/lp0` without running the service as root) —
that only takes effect in a new login session, so log out/in (or
reboot) once before the service can actually print.

## Coexisting with CUPS

If you also want the M110S reachable as a normal shared network
printer (any device, standard OS print dialog), CUPS can run
alongside this service on the same Pi without conflict — both just
open `/dev/usb/lp0`, write, and close per job, the same access pattern,
so as long as two jobs don't land at the literal same instant there's
no contention. The one real requirement: set the CUPS queue up as
**raw** (no driver/PPD doing its own rasterization) if anything is
meant to send our exact pre-built ESC/POS bytes through it — a
rendering PPD reintroduces the exact class of problem the Windows
GDI path had.

## Endpoints

Same contract as `scripts/print_agent.py` minus the loaded-size pair:
`GET /health` (lists both printers + whether each is connected),
`GET /print-queue`, `POST /print-queue/flush`, `POST /print/{code}`.

## Two printers (one per label size)

The Pi drives two printers, so there's no roll swapping and no
`/loaded-size` state — each label goes to the printer holding its size:

| Size | Printer | Device (udev link) | x_offset_mm |
|---|---|---|---|
| 40x30 | Phomemo M128 (USB `09c5:583e`, reports as YiDa YD583) | `/dev/label-40x30` | 2 |
| 20x10 | Phomemo M110S (USB `0483:5740`, Jieli) | `/dev/label-20x10` | 0 |

`99-wheresdat-labels.rules` creates the links by USB vendor:product, so
which port each printer is in doesn't matter (lp0/lp1 order isn't stable,
and both report placeholder serials).

**Alignment.** The M128 ignores the center-justify command and starts its
raster ~2mm left of the label edge; `x_offset_mm` pads the image's left
side to compensate. Its roll floats on a loose axle (shimmed on the right
so it can't walk), so after reloading a roll, re-measure: print a
mm-ruler test pattern, read which mark sits at the label's left edge
(after a feed or two — it settles), and put that number in
`printers.json` next to the agent, e.g. `{"40x30": {"x_offset_mm": 2}}`,
then restart the service.

A printer that's asleep/off drops off USB entirely; the agent checks the
device exists before each write and returns 503 "not connected" instead
of silently "printing" into nothing.
