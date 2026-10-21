#!/usr/bin/env python3
"""Deterministic log generator for level 3 (seeded; reproducible)."""
import os, random
home = os.environ.get("SQ_HOME") or os.path.expanduser("~")
logs = os.path.join(home, "terminal", "logs")
os.makedirs(logs, exist_ok=True)

rng = random.Random(30303)
ips = ["10.0.0.5", "10.0.0.6", "10.0.0.7", "10.0.0.8", "10.0.0.9"]
weights = [10, 12, 55, 9, 14]
urls = ["/", "/login", "/api/data", "/static/app.js", "/admin", "/missing"]
statuses = [200, 200, 200, 301, 404, 500, 403]
with open(os.path.join(logs, "access.log"), "w") as fh:
    for i in range(2000):
        ip = rng.choices(ips, weights=weights)[0]
        url = rng.choice(urls)
        st = 404 if url == "/missing" else rng.choice(statuses)
        hour = rng.choices(range(24), weights=[1]*8 + [9]*2 + [1]*14)[0]
        tag = "ERROR" if st == 500 else "ok"
        fh.write(f"{ip} 2026-03-01T{hour:02d}:00:00 {st} {url} {tag}\n")

rng2 = random.Random(50505)
ips2 = ["172.16.0.2", "172.16.0.3", "172.16.0.4"]
with open(os.path.join(logs, "incident.log"), "w") as fh:
    for i in range(1500):
        ip = rng2.choice(ips2)
        st = rng2.choices([200, 404, 500, 302], weights=[60, 15, 20, 5])[0]
        hour = rng2.choices(range(24), weights=[1]*13 + [20] + [1]*10)[0]
        ua = "curl/8.0"
        if i == 777:
            ua = "Mozilla/5.0 KEY=STREAM-PARSED-99"
        fh.write(f'{ip} 2026-04-02T{hour:02d}:15:00 {st} /op "{ua}"\n')
