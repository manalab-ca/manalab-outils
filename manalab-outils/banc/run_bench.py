import asyncio, json, statistics
from playwright.async_api import async_playwright
decks = json.load(open('precons.json')) + json.load(open('cedh.json')) + json.load(open('user.json'))
JS = '''(D) => { var L = window.__labo; var out = [];
  D.forEach(function (x) {
    var miss = [], main = {};
    Object.keys(x.main).forEach(function (n) { var c = L.find(n); if (c) main[c.n] = (main[c.n] || 0) + x.main[n]; else miss.push(n); });
    var cm = x.commanders.map(function (n) { var c = L.find(n); return c ? c.n : null; }).filter(Boolean);
    var d = { id: "bench-" + x.name, name: x.name, format: "commander", commanders: cm, main: main, prints: {}, combos: [] };
    var P = L.powerIndex(d), B = L.estimateBracket(d, L.findCombos(d)), C = L.confidence(d);
    out.push({ name: x.name, tier: x.tier, power: +P.score.toFixed(2), parts: P.parts.map(function (p) { return +p.v.toFixed(2); }), bracket: B.b, gc: B.gc.length, conf: +C.r.toFixed(3), missCards: C.miss.map(function (c) { return c.n; }), notFound: miss });
  });
  return out; }'''
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = await b.new_page()
        await pg.goto('http://localhost:8768/index.html#deck'); await pg.wait_for_selector('.hero-in', timeout=90000)
        await pg.evaluate('__labo.loadCombos()'); await pg.wait_for_function('__labo.cbReady()', timeout=90000)
        res = await pg.evaluate(JS, decks)
        await b.close()
    json.dump(res, open('bench_result.json', 'w'), indent=1, ensure_ascii=False)
    for tier in ('precon', 'cedh', 'user'):
        R = [r for r in res if r['tier'] == tier]
        pw = [r['power'] for r in R]; cf = [r['conf'] for r in R]
        br = {}; [br.__setitem__(r['bracket'], br.get(r['bracket'], 0) + 1) for r in R]
        print(f"{tier:7s} n={len(R):3d} puissance moy {statistics.mean(pw):.2f} min {min(pw):.1f} max {max(pw):.1f} | brackets {dict(sorted(br.items()))} | compréhension moy {statistics.mean(cf):.1%} min {min(cf):.1%}")
    for r in res:
        if r['tier'] != 'precon': print("  ", r['name'], r['power'], "B" + str(r['bracket']), f"{r['conf']:.0%}", r['notFound'][:4])
    nf = [n for r in res for n in r['notFound']]
    print("cartes introuvables:", len(nf), sorted(set(nf))[:30])
    from collections import Counter
    mc = Counter(n for r in res for n in r['missCards'])
    print("cartes les plus souvent incomprises:", mc.most_common(40))
    top = sorted([r for r in res if r['tier']=='precon'], key=lambda r: -r['power'])[:6]
    print("precons les plus forts:", [(r['name'], r['power'], r['bracket']) for r in top])
asyncio.run(main())
