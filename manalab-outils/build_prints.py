# Build prints.json: every printing (set code + collector number) of every card, from Forge edition files.
import os, re, json, sys, glob

RES, OUT, CARDS = sys.argv[1], sys.argv[2], sys.argv[3]
TODAY = __import__("datetime").date.today().isoformat()
SKIP = {"tokens", "other", "metadata"}

cards = json.load(open(CARDS, encoding="utf-8"))
ni = cards["cols"].index("n")
known = {}
for r in cards["rows"]:
    full = r[ni]
    known[full.lower()] = full
    if " // " in full:
        known.setdefault(full.split(" // ")[0].lower(), full)

sets = []          # [code, name, date, type, scryCode]
treat = ["", ]     # treatment labels
prints = {}        # full card name -> [[setIdx, num, rarity, treatIdx, artist]]
artists = [""]
art_idx = {"": 0}
unmatched = set()

for f in sorted(glob.glob(os.path.join(RES, "editions", "*.txt"))):
    txt = open(f, encoding="utf-8", errors="replace").read()
    meta, sec, rows = {}, None, []
    for line in txt.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^\[(.+)\]$", s)
        if m:
            sec = m.group(1).lower()
            continue
        if sec == "metadata":
            if "=" in s:
                k, v = s.split("=", 1)
                meta[k.strip()] = v.strip()
            continue
        if sec is None or sec in SKIP or "token" in sec:
            continue
        m = re.match(r"^(\S+)\s+([CURMSLT])\s+(.+?)(?:\s+@(.*?))?(?:\s+\$.*)?$", s)
        if not m:
            continue
        rows.append((m.group(1), m.group(2), m.group(3).strip(), (m.group(4) or "").strip(), "" if sec == "cards" else sec))
    code = meta.get("Code")
    if not code or not rows:
        continue
    date = meta.get("Date", "1993-01-01")
    if date > TODAY:
        continue
    si = len(sets)
    sets.append([code, meta.get("Name", code), date, meta.get("Type", ""), (meta.get("ScryfallCode") or code).lower()])
    for num, rar, name, artist, tsec in rows:
        full = known.get(name.lower())
        if not full:
            unmatched.add(name)
            continue
        if tsec not in treat:
            treat.append(tsec)
        if artist not in art_idx:
            art_idx[artist] = len(artists); artists.append(artist)
        prints.setdefault(full, []).append([si, num, rar, treat.index(tsec), art_idx[artist]])

# newest first
for k in prints:
    prints[k].sort(key=lambda p: (sets[p[0]][2], sets[p[0]][0], [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p[1])]), reverse=True)

json.dump({"sets": sets, "treat": treat, "artists": artists, "prints": prints}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
n = sum(len(v) for v in prints.values())
print("sets", len(sets), "cards", len(prints), "printings", n, "unmatched", len(unmatched), "size", os.path.getsize(OUT))
print(sorted(unmatched)[:15])
