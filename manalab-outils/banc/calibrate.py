"""ManaLab — calibrate the power index on labelled decks.

  python3 calibrate.py                 # measure: how many reference decks fall in their range
  python3 calibrate.py --fit           # fit the weights, show the gain
  python3 calibrate.py --fit --apply ../index.html   # write the new weights into the site
  options: --url http://localhost:8768/index.html   --reports reports.json (players' ratings exported from Supabase)

Ground truth (anchors.json): the 180 official precons (low power, mean 3.0), cEDH lists (9.2+), decks of known
strength with a range, random piles of cards (very low), and the ratings players send with "Does this score feel wrong?".
"""
import argparse, asyncio, json, math, os, re, statistics, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
F = ["fast", "tut", "gc", "combo", "inter", "draw", "curve", "value", "ctrl", "qual", "press"]
ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:8768/index.html")
ap.add_argument("--fit", action="store_true"); ap.add_argument("--apply")
ap.add_argument("--reports", help="JSON export of the Supabase table reports (kind=score with a rating)")
ap.add_argument("--piles", type=int, default=24)
ap.add_argument("--min", type=float, default=0, help="fail (exit 1) when fewer reference decks than this share fall in their range")
args = ap.parse_args()
anchors = json.load(open(os.path.join(HERE, "anchors.json")))
def load_reports(p):
    if p.endswith(".csv"):
        import csv
        return list(csv.DictReader(open(p, encoding="utf-8")))
    return json.load(open(p, encoding="utf-8"))
if args.reports and os.path.exists(args.reports):
    for r in load_reports(args.reports):
        ctx = r.get("context") or {}
        if isinstance(ctx, str): ctx = json.loads(ctx)
        rt, dk = ctx.get("rating"), ctx.get("deck")
        rt = float(rt) if rt else None
        if rt and dk and dk.get("c"):
            main = {}
            for m in dk.get("m", []):
                if isinstance(m, list): main[m[0]] = m[1]
                else: main[m] = 1
            anchors.append({"name": "avis: " + dk.get("n", "?"), "group": "avis", "commanders": dk["c"], "main": main, "lo": max(1, rt - 0.75), "hi": min(10, rt + 0.75)})
JS = '''([A, piles]) => { var L = window.__labo, out = [];
  var mk = function (x, i) { if (x.list) { var d = L.importList(x.list); d.id = "cal" + i; return d; }
    var main = {}; Object.keys(x.main).forEach(function (n) { var c = L.find(n); if (c) main[c.n] = (main[c.n] || 0) + x.main[n]; });
    return { id: "cal" + i, name: x.name, format: "commander", commanders: x.commanders.map(function (n) { var c = L.find(n); return c ? c.n : n; }).filter(Boolean), main: main, prints: {}, combos: [] }; };
  A.forEach(function (x, i) { var d = mk(x, i), k = L.powerCounts(d); out.push({ i: i, phi: L.pwPhi(k), score: L.powerIndex(d).score }); });
  // random piles: a commander and 62 random cards of its colours: the bottom of the scale
  var all = L.allCards(), cmds = ["Phenax, God of Deception", "Ayara, First of Locthwain", "Krenko, Mob Boss", "Atraxa, Praetors' Voice", "Omnath, Locus of Rage", "Edgar Markov", "Y'shtola, Night's Blessed", "Aesi, Tyrant of Gyre Strait"];
  for (var p = 0; p < piles; p++) { var cn = cmds[p % cmds.length], c = L.find(cn), id = c.i, seed = p * 7919 + 17;
    var rand = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    var pool = all.filter(function (x) { return !x.isLand && (x.lg & 2) && x.i.split("").every(function (ch) { return id.indexOf(ch) >= 0; }); });
    var main = {}, cnt = 0; while (cnt < 62) { var x = pool[Math.floor(rand() * pool.length)]; if (!main[x.n] && x.n !== c.n) { main[x.n] = 1; cnt++; } }
    main[id.indexOf("G") >= 0 ? "Forest" : id.indexOf("B") >= 0 ? "Swamp" : id.indexOf("R") >= 0 ? "Mountain" : id.indexOf("U") >= 0 ? "Island" : "Plains"] = 37;
    var d = { id: "pile" + p, name: "pile", format: "commander", commanders: [c.n], main: main, prints: {}, combos: [] }, k = L.powerCounts(d);
    out.push({ pile: true, name: "pile " + cn, phi: L.pwPhi(k), score: L.powerIndex(d).score }); }
  return { rows: out, W: L.PW_W }; }'''
async def features():
    async with async_playwright() as p:
        b = await p.chromium.launch(**({"executable_path": "/usr/bin/google-chrome"} if os.path.exists("/usr/bin/google-chrome") else {}), args=["--no-sandbox"])
        pg = await b.new_page()
        await pg.add_init_script('localStorage.setItem("labo.started","true")')
        await pg.goto(args.url); await pg.wait_for_function('document.getElementById("loading").hidden', timeout=120000)
        await pg.evaluate('__labo.loadCombos()'); await pg.wait_for_function('__labo.cbReady()', timeout=120000)
        res = await pg.evaluate(JS, [anchors, args.piles])
        await b.close()
    return res
res = asyncio.run(features())
rows, W0 = res["rows"], res["W"]
data = []
for r in rows:
    if r.get("pile"): data.append(dict(name=r["name"], group="pile", lo=1.0, hi=2.6, phi=r["phi"], score=r["score"]))
    else:
        a = anchors[r["i"]]; data.append(dict(name=a["name"], group=a["group"], lo=a["lo"], hi=a["hi"], phi=r["phi"], score=r["score"]))
def score_of(W, phi): return max(1, min(10, W["b"] + sum(W[f] * phi[f] for f in F)))
def report(W, title):
    print("\n" + title)
    groups = {}
    for d in data:
        s = score_of(W, d["phi"]); ok = d["lo"] <= s <= d["hi"]
        g = groups.setdefault(d["group"], [0, 0, []]); g[0] += ok; g[1] += 1; g[2].append(s)
    tot_ok = sum(g[0] for g in groups.values()); tot = sum(g[1] for g in groups.values())
    for k, (ok, n, ss) in groups.items(): print("  %-8s %3d/%-3d dans la fourchette · moyenne %.2f · min %.1f · max %.1f" % (k, ok, n, statistics.mean(ss), min(ss), max(ss)))
    print("  TOTAL    %d/%d (%.0f %%)" % (tot_ok, tot, 100 * tot_ok / tot))
    for d in data:
        if d["group"] not in ("precon", "pile"):
            s = score_of(W, d["phi"]); print("    %s %-42s %.2f  [%s–%s]" % ("✓" if d["lo"] <= s <= d["hi"] else "✗", d["name"][:42], s, d["lo"], d["hi"]))
    return tot_ok / tot
before = report(W0, "Poids actuels")
if args.fit:
    import numpy as np
    from scipy.optimize import minimize
    keys = ["b"] + F
    x0 = np.array([W0.get(k, 0) for k in keys], dtype=float)
    P = np.array([[d["phi"][f] for f in F] for d in data]); lo = np.array([d["lo"] for d in data]); hi = np.array([d["hi"] for d in data])
    wt = np.array([1.0 if d["group"] in ("precon",) else 6.0 if d["group"] == "pile" else 25.0 for d in data])
    pre = np.array([d["group"] == "precon" for d in data])
    def loss(x):
        s = np.clip(x[0] + P @ x[1:], 1, 10)
        h = np.maximum(0, lo - s) + np.maximum(0, s - hi)
        L = np.sum(wt * h * h) + 200 * (np.mean(s[pre]) - 3.0) ** 2
        L += 0.5 * np.sum((x - x0) ** 2)  # stay close to the current weights: change only what the data asks for
        return L
    bounds = [(-1, 3)] + [(0, 3)] * len(F)
    r = minimize(loss, x0, method="L-BFGS-B", bounds=bounds)
    W = {k: round(float(v), 3) for k, v in zip(keys, r.x)}
    after = report(W, "Poids calibrés")
    print("\n  poids :", json.dumps(W))
    if args.apply and after >= before:
        p = args.apply; s = open(p, encoding="utf-8").read()
        fit = {"n": len(data), "inRange": round(after, 3), "groups": sorted(set(d["group"] for d in data))}
        block = "// PW_WEIGHTS_BEGIN\nvar PW_W = " + json.dumps(W) + ";\nvar PW_FIT = " + json.dumps(fit, ensure_ascii=False) + ";\n// PW_WEIGHTS_END"
        s = re.sub(r"// PW_WEIGHTS_BEGIN.*?// PW_WEIGHTS_END", lambda m: block, s, flags=re.S)
        open(p, "w", encoding="utf-8").write(s); print("  → écrit dans", p)
    elif args.apply: print("  → pas appliqué : le calibrage ne fait pas mieux que les poids actuels")
score_now = before if not args.fit else after
if args.min and score_now < args.min:
    print("\nÉCHEC : %.0f %% des decks de référence dans leur fourchette, il en faut %.0f %%." % (100 * score_now, 100 * args.min)); sys.exit(1)
