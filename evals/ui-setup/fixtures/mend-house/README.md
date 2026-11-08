# Mend House pilot

This is an independently authored synthetic fixture. All names and contact details are invented. It uses ordinary HTML, CSS and JavaScript with no external assets, packages or build step. It does not contain source copied from a real product or from a skill implementation.

Serve this directory with a static server, for example `python3 -m http.server 8042`, then open `http://localhost:8042`. A shared HTTP origin lets the three pages use the same browser storage. Opening files directly may give each page separate storage in some browsers. Example arrival references: `1204`, `1205`, `1206`.

The volunteer team uses a laptop at the desk. A separate borrowed tablet is intended to stay on the arrival screen at the doorway, where guests stand and may be carrying an item. Hosts also sometimes check the list on a phone. The tablet should move on promptly after each guest, but the pilot has only been tried on the desk laptop. Volunteers currently write repair progress and shift notes on paper.

The current implementation is a local demonstration of booking and arrival interactions. It has no backend, accounts, delivery service or cross-device transport. Guest records persist in the current browser until its storage is cleared. The fixture scope is the three pages here; there are no additional screens, screenshots or private production systems to inspect.
