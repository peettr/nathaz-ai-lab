"""R4 preregistered CPU scorer. Input is merged group JSONL, no AI integration here."""
import argparse, csv, datetime as dt, json, math, pathlib
from collections import defaultdict
import numpy as np
from scipy.stats import binomtest

TH = 25.7

def score(events_path, controls_path, input_path, output_path, *, budget_truncated=False, s0_gate=False, deviation_affects_main=False):
    events = sorted(csv.DictReader(open(events_path)), key=lambda x: int(x['order']))
    controls = sorted(csv.DictReader(open(controls_path)), key=lambda x: int(x['order']))
    assert len(events) == 100 and len(controls) == 100
    assert [int(x['order']) for x in events] == [int(x['order']) for x in controls] == list(range(100))
    units = [x for pair in zip(events, controls) for x in (('event', pair[0]), ('control', pair[1]))]
    assert all(e['id'] == c['event_id'] for e,c in zip(events,controls))
    records = defaultdict(list)
    for line in pathlib.Path(input_path).read_text().splitlines():
        if not line.strip(): continue
        try: r = json.loads(line)
        except ValueError: continue  # only a disk-full trailing line may be truncated
        if r['status'] == 'ok': records[(r['unit_index'], r['kind'], r.get('seed'))].append(r)
    if any(len(v) != 1 for v in records.values()): raise ValueError('duplicate successful key')
    scored, excluded = [], []
    for i, (kind, source) in enumerate(units):
        if kind == 'control' and source['phase'] == 'missing':
            excluded.append({'index': i, 'reason': 'S0 unmatched control, not an attempted unit'});continue
        b = records.get((i, 'baseline', None), [])
        members = [records[(i, 'member', seed)][0] for seed in range(101, 111) if records.get((i, 'member', seed))]
        if len(b) != 1 or len(members) < 8:
            excluded.append({'index': i, 'reason': 'baseline missing or <8 members; rerun once before final exclusion'});continue
        try:
            expected_id = source['id'] if kind == 'event' else source['event_id']
            assert b[0]['event_id'] == expected_id and all(x['event_id'] == expected_id for x in members)
            h, hn = float(b[0]['fg_wide']['ms']), float(b[0]['fg_narrow']['ms'])
            obs = float(source['obs_kt'] if kind == 'event' else source['max_kt']) * .514444
            variants = {name: np.array([float(m['methods'][method][window]['ms']) for m in members])
                        for name, method, window in [('diagnostic', 'diagnostic', 'wide'), ('factor16777', 'factor16777', 'wide'),
                                                     ('hrrrcast_without_vvel', 'hrrrcast_without_vvel', 'wide'), ('narrow', 'diagnostic', 'narrow')]}
            hsame = float(b[0]['hrrr_formula_wide']['ms'])
            if not all(math.isfinite(v) and v > 0 for v in (h, hn, hsame, obs)) or not all(np.isfinite(a).all() for a in variants.values()): raise ValueError('nonfinite')
        except (KeyError, TypeError, ValueError, AssertionError) as ex:
            excluded.append({'index': i, 'reason': f'window/obs missing: {ex!r}'});continue
        scored.append(dict(index=i, order=int(source['order']), kind=kind, day=source['utc'][:10], year=source['utc'][:4],
                           n=len(members), obs_ms=obs, ai=variants['diagnostic'], h=h, hn=hn, hsame=hsame,
                           variants=variants, phase=source.get('phase', 'event')))
    scored.sort(key=lambda x:x['index'])
    byday = defaultdict(list)
    for row in scored: byday[row['day']].append(row)
    days = sorted(byday)
    rng = np.random.default_rng(20261107)  # §3: day clusters, sorted and sampled jointly
    draws = [rng.choice(len(days), len(days), replace=True) for _ in range(5000)] if days else []
    def subset(d): return [r for j in d for r in byday[days[j]]]
    def vals(rows, variant='diagnostic', baseline='h', aggregation='any'):
        e=[r for r in rows if r['kind']=='event'];c=[r for r in rows if r['kind']=='control']
        if not e or not c:return None
        aa=[r['ai'] if variant=='diagnostic' else r['variants'][variant] for r in rows]
        hh=[r[baseline] for r in rows]
        probs=np.array([np.mean(a>=TH) for a in aa]); predicted=np.array([np.any(a>=TH) if aggregation=='any' else np.mean(a>=TH)>=.3 for a in aa]);hpred=np.array([h>=TH for h in hh]); y=np.array([r['kind']=='event' for r in rows]);
        ev=y;co=~y
        yf=y.astype(float); pf=predicted.astype(float);hf=hpred.astype(float)
        ratios=np.array([(np.max(a) if aggregation=='any' else np.median(a))/h for a,h in zip(aa,hh)])
        return dict(hit_ai=float(predicted[ev].mean()),hit_hrrr=float(hpred[ev].mean()),hit_diff=float(predicted[ev].mean()-hpred[ev].mean()),
                    false_ai=float(predicted[co].mean()),false_hrrr=float(hpred[co].mean()),false_diff=float(predicted[co].mean()-hpred[co].mean()),
                    peak_ratio_event=float(np.median(ratios[ev])),peak_ratio_control=float(np.median(ratios[co])),
                    bs_p_diff=float(np.mean((probs-yf)**2)-np.mean((hf-yf)**2)),
                    bs_binary_diff=float(np.mean((pf-yf)**2)-np.mean((hf-yf)**2)),
                    peirce_diff=float(predicted[ev].mean()-predicted[co].mean()-hpred[ev].mean()+hpred[co].mean()))
    def evaluate(rows, variant='diagnostic', baseline='h', aggregation='any', samples=draws):
        point=vals(rows,variant,baseline,aggregation)
        if point is None:return {'point':None,'ci':None,'valid_draws':0}
        reps=[vals(subset(d),variant,baseline,aggregation) for d in samples]
        good=[r for r in reps if r is not None]
        ci={k: {'lower05':float(np.percentile([r[k] for r in good],5)), 'upper95':float(np.percentile([r[k] for r in good],95))} for k in point} if len(good)>=4900 else None # §3
        return {'point':point,'ci':ci,'valid_draws':len(good)}
    main=evaluate(scored)
    p, ci = main['point'],main['ci']
    # §2.3, §4: numerical gates require valid bootstrap and nonempty cohorts.
    hit=bool(ci and ci['hit_diff']['lower05']>-.15 and p['hit_diff']>=-.05)
    false=bool(ci and ci['false_diff']['upper95']<.15 and p['false_diff']<=.05)
    peak=bool(ci and p['peak_ratio_event']>=1 and ci['peak_ratio_event']['lower05']>=.9)
    no_information=bool(ci and p['false_ai']<=.05 and p['false_hrrr']<=.05 and ci['false_diff']['lower05']<=0<=ci['false_diff']['upper95']) # §2.3
    exploratory= len(excluded)>20 or s0_gate or budget_truncated or deviation_affects_main # §2.3, §2.2
    verdict=('探索性' if exploratory else '不判' if not ci else '不通过' if not(hit and false and peak) else '不判' if no_information else '通过') # §2.3: ordered branches
    def rank(field):
        rows=sorted(scored,key=lambda r:(-field(r),r['order']))
        ne=sum(r['kind']=='event' for r in scored)
        return {str(k): {'event_count':sum(r['kind']=='event' for r in rows[:k]),
                         'capture':sum(r['kind']=='event' for r in rows[:k])/ne if ne else None,
                         'precision':sum(r['kind']=='event' for r in rows[:k])/min(k,len(rows)) if rows else None} for k in (10,25,50,100)} # §4
    coverage={kind: {'n':len(z),'covered':sum(min(r['ai'])<=r['obs_ms']<=max(r['ai']) for r in z),
                     'fraction':sum(min(r['ai'])<=r['obs_ms']<=max(r['ai']) for r in z)/len(z) if z else None}
              for kind in ('event','control') for z in [[r for r in scored if r['kind']==kind]]} # §4
    report={k:evaluate(scored,*args) for k,args in {
        's2_original':('diagnostic','h','p03'),'factor16777':('factor16777','h','any'),
        'hrrrcast_without_vvel':('hrrrcast_without_vvel','h','any'),
        'narrow':('narrow','hn','any'),'same_formula_hrrr':('diagnostic','hsame','any')}.items()} # §4 report-only
    # §4: subset sensitivity uses the same predeclared day draws, restricted to the subset's own sorted day list.
    def subset_eval(rows):
        if not rows:return None
        dd=defaultdict(list)
        for r in rows:dd[r['day']].append(r)
        keys=sorted(dd); local=np.random.default_rng(20261107)
        smp=[local.choice(len(keys),len(keys),replace=True) for _ in range(5000)]
        pp=vals(rows); rr=[vals([r for j in d for r in dd[keys[j]]]) for d in smp];ok=[v for v in rr if v]
        return {'point':pp,'valid_draws':len(ok),'ci':{k:{'lower05':float(np.percentile([v[k] for v in ok],5)),'upper95':float(np.percentile([v[k] for v in ok],95))} for k in pp} if len(ok)>=4900 else None}
    near=subset_eval([r for r in scored if r['phase'] in ('near','近阈','event')])
    dev=subset_eval([r for r in scored if r['year']!='2022' and not ('2024-05-08'<=r['day']<='2024-06-15')])
    ev=[r for r in scored if r['kind']=='event'];discord_a=sum(np.any(r['ai']>=TH) and r['h']<TH for r in ev);discord_h=sum(not np.any(r['ai']>=TH) and r['h']>=TH for r in ev)
    mcnemar=binomtest(min(discord_a,discord_h),discord_a+discord_h,.5).pvalue if discord_a+discord_h else 1.0 # §4 exact two-sided
    out={'cohort':{'event':len(ev),'control':len(scored)-len(ev),'excluded':excluded},'main':main,
         'gates':{'hit':hit,'false_numerical':false,'peak':peak,'false_uninformative':no_information,'exploratory':exploratory,'verdict':verdict},
         'report_only':report,'near_threshold_only_false_alarm':near,'without_developer_period':dev,
         'topk':{'ai':rank(lambda r:max(r['ai'])),'hrrr':rank(lambda r:r['h'])},'coverage_thunderstorm':coverage,
         'mcnemar':{'discord_ai_only':discord_a,'discord_hrrr_only':discord_h,'p_exact_two_sided':mcnemar},
         'better_than_hrrr_eligible_for_review':bool(p and ci and p['hit_diff']>0 and mcnemar<.05 and ci['false_diff']['upper95']<0)} # §4
    output_path=pathlib.Path(output_path); output_path.parent.mkdir(parents=True,exist_ok=True)
    with output_path.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--events',required=True);ap.add_argument('--controls',required=True);ap.add_argument('--input',required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--budget-truncated',action='store_true');ap.add_argument('--s0-gate',action='store_true');ap.add_argument('--deviation-affects-main',action='store_true')
    x=ap.parse_args();out=score(x.events,x.controls,x.input,x.output,budget_truncated=x.budget_truncated,s0_gate=x.s0_gate,deviation_affects_main=x.deviation_affects_main)
    print(json.dumps({'cohort':out['cohort'],'gates':out['gates'],'output':x.output},ensure_ascii=False))
