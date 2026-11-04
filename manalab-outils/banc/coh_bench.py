import asyncio, json, statistics, random
from playwright.async_api import async_playwright
decks = json.load(open('precons.json')) + json.load(open('cedh.json')) + json.load(open('user.json'))
JS = '''(D) => { var L = window.__labo; var out = [];
  var mk = function (x) { var main = {}; Object.keys(x.main).forEach(function (n) { var c = L.find(n); if (c) main[c.n] = (main[c.n] || 0) + x.main[n]; });
    var cm = x.commanders.map(function (n) { var c = L.find(n); return c ? c.n : null; }).filter(Boolean);
    return { id: "coh-" + x.name, name: x.name, format: "commander", commanders: cm, main: main, prints: {}, combos: [] }; };
  D.forEach(function (x) { var d = mk(x), C = L.coherence(d), th = L.deckThemes(d);
    out.push({ name: x.name, tier: x.tier, coh: C ? +C.score.toFixed(2) : null, raw: C ? +C.raw.toFixed(3) : null, parts: C ? C.parts : null, themes: th.map(function (t) { return t.t.n + (t.cmd ? "*" : "") + " " + t.cnt; }) }); });
  return out; }'''
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = await b.new_page()
        await pg.add_init_script('localStorage.setItem("labo.started","true")'); await pg.goto('http://localhost:8768/index.html#deck'); await pg.wait_for_function('document.getElementById("loading").hidden', timeout=90000)
        await pg.evaluate('__labo.loadCombos()'); await pg.wait_for_function('__labo.cbReady()', timeout=90000)
        # random "pile" decks: commander + 62 random legal in-colour nonland cards + basics
        rnd = await pg.evaluate('''(() => { var L = window.__labo, out = []; var cmds = ["Phenax, God of Deception","Ayara, First of Locthwain","Krenko, Mob Boss","Atraxa, Praetors' Voice","Omnath, Locus of Rage","Edgar Markov"];
          var rows = []; for (var n in {}) {}
          return cmds; })()''')
        res = await pg.evaluate(JS, decks)
        piles = await pg.evaluate('''(cmds) => { var L = window.__labo, out = [];
          var all = L.allCards();
          cmds.forEach(function (cn, k) { var c = L.find(cn), id = c.i; var pool = all.filter(function (x) { return !x.isLand && (x.lg & 2) && x.i.split("").every(function (ch) { return id.indexOf(ch) >= 0; }) && x.pr >= 1; });
            for (var rep = 0; rep < 3; rep++) { var main = {}, seed = k * 7 + rep * 13 + 1; var rand = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
              var cnt = 0; while (cnt < 62) { var x = pool[Math.floor(rand() * pool.length)]; if (!main[x.n]) { main[x.n] = 1; cnt++; } } main["Swamp"] = 37;
              var d = { id: "pile-" + cn + rep, name: "pile", format: "commander", commanders: [c.n], main: main, prints: {}, combos: [] }; var C = L.coherence(d);
              out.push({ name: "pile " + cn + " " + rep, coh: +C.score.toFixed(2), raw: +C.raw.toFixed(3), themes: L.deckThemes(d).map(function (t) { return t.t.n + " " + t.cnt; }) }); } });
          return out; }''', rnd)
        await b.close()
    json.dump(res, open('coh_result.json', 'w'), indent=1, ensure_ascii=False)
    for tier in ('precon', 'cedh', 'user'):
        R = [r for r in res if r['tier'] == tier and r['raw'] is not None]
        raws = sorted(r['raw'] for r in R)
        print(tier, len(R), 'raw moy %.3f min %.3f p10 %.3f p90 %.3f max %.3f' % (statistics.mean(raws), raws[0], raws[len(raws)//10], raws[len(raws)*9//10], raws[-1]), 'score moy %.2f' % statistics.mean(r['coh'] for r in R))
    pr = [p['raw'] for p in piles]; print('piles raw moy %.3f min %.3f max %.3f' % (statistics.mean(pr), min(pr), max(pr)), 'score moy %.2f' % statistics.mean(p['coh'] for p in piles))
    for r in res:
        if r['tier'] != 'precon': print('  ', r['name'], r['coh'], r['themes'])
    for r in sorted([r for r in res if r['tier']=='precon'], key=lambda r: r['raw'])[:5] + sorted([r for r in res if r['tier']=='precon'], key=lambda r: -r['raw'])[:5]: print('  P', r['name'], r['coh'], r['themes'])
    from collections import Counter
    print('thèmes principaux précons:', Counter(r['themes'][0].split(' ')[0] if r['themes'] else '-' for r in res if r['tier']=='precon').most_common(30))
    print('sans thème:', sum(1 for r in res if r['tier']=='precon' and not r['themes']))
    for p in piles[:6]: print('  pile', p['coh'], p['themes'])
asyncio.run(main())
