import json,sys
c=json.load(open('cards.json'));cols=c['cols'];ix={k:i for i,k in enumerate(cols)}
sf=json.load(open('tags/scryfall_roles.json'))
rows=[r for r in c['rows'] if 'Land' not in r[ix['t']].split() and not r[ix['n']].startswith('A-') and not r[ix['up']]]
def front(n): return n.split(' // ')[0]
TEST={
 "ramp":lambda g: bool(g.get('mana') or g.get('ramp') or g.get('treng') or g.get('treas',0)>=2 or g.get('ritual') or 'r' in g.get('sf','')),
 "draw":lambda g: bool(g.get('draw') or g.get('engine')),
 "rem":lambda g: bool(g.get('rem') or 'k' in g.get('sf','')),
 "wipe":lambda g: bool(g.get('wipe') or g.get('wipe1') or 'w' in g.get('sf','')),
 "ae":lambda g: bool(g.get('ae') or 'a' in g.get('sf','')),
 "recur":lambda g: bool(g.get('recur') or 'c' in g.get('sf','')),
 "tutor":lambda g: bool(g.get('tutor') or g.get('tut') or 't' in g.get('sf','')),
 "ctr":lambda g: bool(g.get('ctr') or 'x' in g.get('sf','')),
 "prot":lambda g: bool(g.get('prot') or 'p' in g.get('sf','')),
 "sacout":lambda g: 'F' in g.get('cz',''),
 "deathtrig":lambda g: 'D' in g.get('cz',''),
 "fin":lambda g: bool(g.get('fin')),
 "burn":lambda g: bool(g.get('burn')),
}
res={}
for k,f in TEST.items():
    S=set(sf[k])|set(front(x) for x in sf[k])
    tp=fp=fn=0; fps=[]; fns=[]
    for r in rows:
        n=r[ix['n']]; g=r[ix['g']]
        a=f(g); b=(n in S or front(n) in S)
        if a and b: tp+=1
        elif a: fp+=1; fps.append((r[ix['pr']],n))
        elif b: fn+=1; fns.append((r[ix['pr']],n))
    prec=tp/(tp+fp) if tp+fp else 0; rec=tp/(tp+fn) if tp+fn else 0
    res[k]={"tp":tp,"fp":fp,"fn":fn,"prec":round(prec,3),"rec":round(rec,3),"fp_top":[n for _,n in sorted(fps,reverse=True)[:25]],"fn_top":[n for _,n in sorted(fns,reverse=True)[:25]]}
    print(f"{k:10s} accord-précision {prec:5.1%}  rappel {rec:5.1%}   (tp {tp}, seulement nous {fp}, seulement Scryfall {fn})")
json.dump(res,open('tags/compare.json','w'),indent=1,ensure_ascii=False)
