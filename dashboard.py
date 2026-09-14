import json
from pathlib import Path
from flask import Flask, jsonify, request, Response

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONFIG = ROOT / "config.json"
CONFIG_EXAMPLE = ROOT / "config.example.json"
STRATEGY = ROOT / "strategie.json"
app = Flask(__name__)


def read_config():
    path = CONFIG if CONFIG.exists() else CONFIG_EXAMPLE
    return json.loads(path.read_text(encoding="utf-8"))

PAGE = r'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KICKBASE Control Center</title><style>
:root{--ink:#153832;--muted:#7d8b86;--line:rgba(38,65,57,.11);--green:#789b79;--green2:#dfe9dc;--gold:#e4c88b;--blue:#789ab5;--white:rgba(255,255,255,.78);--shadow:0 18px 55px rgba(53,67,61,.09)}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font:16px/1.45 Inter,"Segoe UI",Arial,sans-serif;background:linear-gradient(135deg,#f8f6f2 0%,#f5f7f3 46%,#eef2ef 100%);min-height:100vh}.shell{max-width:1440px;margin:0 auto;padding:32px;display:grid;grid-template-columns:220px minmax(0,1fr);gap:26px}.glass{background:var(--white);border:1px solid rgba(255,255,255,.9);box-shadow:var(--shadow);backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px)}
aside{border-radius:28px;padding:24px 17px;min-height:calc(100vh - 64px);display:flex;flex-direction:column}.brand{display:flex;gap:11px;align-items:center;padding:5px 8px 27px;font-weight:750}.logo{width:39px;height:39px;border-radius:13px;background:var(--ink);color:white;display:grid;place-items:center;font-size:20px}.nav{display:grid;gap:7px}.nav button{border:0;background:transparent;color:#6f7f79;text-align:left;padding:12px 13px;border-radius:14px;font:inherit;margin:0;cursor:pointer}.nav button:hover{background:#eef3ef;color:var(--ink)}.nav .active{background:var(--green2);color:var(--ink);font-weight:700}.nav span{display:inline-block;width:28px}.aside-foot{margin-top:auto;padding:14px;border-top:1px solid var(--line)}.live{display:flex;align-items:center;gap:8px;font-size:14px}.dot{width:9px;height:9px;border-radius:50%;background:#6aa875;box-shadow:0 0 0 5px rgba(106,168,117,.12)}
main{min-width:0}.top{display:flex;justify-content:space-between;align-items:center;margin:6px 2px 24px}h1{font-size:clamp(28px,4vw,42px);letter-spacing:-1.5px;margin:0;font-weight:640}.sub{color:var(--muted);font-size:14px;margin-top:4px}.profile{display:flex;align-items:center;gap:10px;padding:9px 14px;border-radius:30px;background:rgba(255,255,255,.58);border:1px solid white}.avatar{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#9eb09d,#617e72);color:#fff;display:grid;place-items:center;font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{border-radius:24px;padding:19px 20px}.label{color:var(--muted);font-size:13px}.value{font-size:25px;font-weight:650;letter-spacing:-.7px;margin-top:5px}.status{color:#557b5e}.workspace{display:grid;grid-template-columns:1.75fr .85fr;gap:16px;margin-top:16px}.market-card{padding:22px;border-radius:28px}.right{display:grid;gap:16px;align-content:start}.control{border-radius:24px;padding:20px}.control.gold{background:linear-gradient(135deg,#fff8e9,#f5e4bd);border-color:#fff8e5}.row{display:flex;justify-content:space-between;gap:12px;align-items:center}h2{font-size:20px;margin:0 0 16px;letter-spacing:-.3px}.hint{font-size:13px;color:#8d7c56;margin:4px 0 16px}.locked{padding:6px 10px;border-radius:20px;background:rgba(255,255,255,.62);font-size:12px;font-weight:700}button{border:0;border-radius:13px;padding:11px 14px;font-weight:700;cursor:pointer;background:var(--ink);color:#fff;width:100%;margin-top:12px}select,input{width:100%;border:1px solid var(--line);background:rgba(255,255,255,.7);border-radius:13px;padding:11px;color:var(--ink);font:inherit;margin-top:7px}.setting+ .setting{margin-top:14px}
.pitch{min-height:465px;border-radius:22px;padding:25px 18px;background:linear-gradient(rgba(255,255,255,.04),rgba(255,255,255,.04)),repeating-linear-gradient(0deg,#86aa82 0,#86aa82 64px,#80a47c 64px,#80a47c 128px);position:relative;border:2px solid rgba(255,255,255,.6)}.pitch:before{content:"";position:absolute;inset:24px;border:2px solid rgba(255,255,255,.48);border-radius:3px}.formation{position:relative;z-index:1;display:grid;grid-template-columns:repeat(12,1fr);grid-template-rows:repeat(4,92px);align-items:center;height:100%}.slot{background:rgba(255,255,255,.92);border-radius:13px;padding:9px 6px;text-align:center;font-size:12px;box-shadow:0 8px 20px rgba(28,61,38,.15);margin:auto;width:92px}.slot b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.slot .small{font-size:11px}.empty-slot{opacity:.65}.market-wide{margin-top:16px}.tablewrap{overflow:auto;max-height:440px}table{width:100%;border-collapse:collapse;min-width:610px}th,td{text-align:left;padding:13px 10px;border-bottom:1px solid var(--line)}th{font-size:12px;color:var(--muted);font-weight:600;position:sticky;top:0;background:#fbfcfa}.player{font-weight:650}.pos,.pill{display:inline-block;padding:5px 8px;border-radius:9px;background:#eef3ef;font-size:12px}.up{color:#568e63}.down{color:#bd6d6d}.neutral{color:var(--muted)}.pill{border-radius:20px;background:#edf2f4}.recommend{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-bottom:1px solid var(--line)}.signal{width:10px;height:10px;border-radius:50%;background:#73a37d}.small{font-size:13px;color:var(--muted)}
button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid rgba(120,155,121,.35);outline-offset:2px}.view{display:none}.view.active{display:block}.pagehead{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.toolbar{display:flex;gap:9px;flex-wrap:wrap}.chip{width:auto;margin:0;background:#edf2ee;color:var(--ink);padding:9px 13px}.chip.active{background:var(--ink);color:white}.clickable{cursor:pointer;transition:.18s transform,.18s box-shadow}.clickable:hover{transform:translateY(-2px);box-shadow:0 12px 26px rgba(38,65,57,.12)}.empty{padding:45px;text-align:center;color:var(--muted)}.modal{position:fixed;inset:0;background:rgba(15,33,28,.28);display:none;place-items:center;padding:20px;z-index:10}.modal.open{display:grid}.dialog{width:min(520px,100%);border-radius:28px;padding:25px;position:relative}.close{position:absolute;right:16px;top:13px;width:38px;height:38px;border-radius:50%;margin:0;padding:0;background:#edf2ee;color:var(--ink);font-size:21px}.detailgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:18px 0}.detailbox{background:#f3f6f3;border-radius:15px;padding:13px}.toast{position:fixed;right:24px;bottom:24px;background:var(--ink);color:white;padding:13px 18px;border-radius:14px;opacity:0;transform:translateY(15px);transition:.2s;z-index:20}@media(max-width:980px){.shell{grid-template-columns:1fr;padding:18px}aside{min-height:auto;padding:12px 15px}.brand{padding:5px}.nav{display:flex;overflow:auto}.nav button{white-space:nowrap}.aside-foot{display:none}.workspace{grid-template-columns:1fr}.kpis{grid-template-columns:1fr 1fr}.profile{display:none}}@media(max-width:560px){.shell{padding:12px}.kpis{grid-template-columns:1fr 1fr;gap:9px}.card{padding:15px}.value{font-size:20px}.market-card{padding:16px}.top{margin-top:8px}.nav button{font-size:14px}.detailgrid{grid-template-columns:1fr}}
</style></head><body><div class="shell"><aside class="glass"><div class="brand"><div class="logo">K</div><div>KICKBASE<br><span class="small">Control Center</span></div></div><div class="nav"><button class="active" data-view="overview"><span>⌂</span>Übersicht</button><button data-view="market"><span>↗</span>Transfermarkt</button><button data-view="squad"><span>♟</span>Kader</button><button data-view="matchday"><span>⚑</span>Spieltag</button><button data-view="rules"><span>⚙</span>Regeln</button></div><div class="aside-foot"><div class="live"><i class="dot"></i> Live verbunden</div><div class="small" style="margin-top:8px">Automatische Aktualisierung</div></div></aside>
<main><header class="top" id="overview"><div><h1>Guten Abend, Lucas</h1><div class="sub" id="subtitle">Bierbanausen · wird geladen …</div></div><button class="profile clickable" onclick="navigate('squad')" style="width:auto;margin:0;color:var(--ink)"><div class="avatar">L</div><div><b>Sike El Schmaler</b><div class="small">Manager · Kader öffnen</div></div></button></header>
<section class="kpis"><div class="card glass clickable" onclick="navigate('rules')"><div class="label">Budget</div><div class="value" id="budget">wird geladen</div></div><div class="card glass clickable" onclick="navigate('squad')"><div class="label">Kaderwert</div><div class="value" id="squadValue">wird geladen</div></div><div class="card glass clickable" onclick="navigate('market')"><div class="label">Offene Gebote</div><div class="value" id="offers">–</div></div><div class="card glass clickable" onclick="toggleTrading()"><div class="label">Systemstatus</div><div class="value status">● Testmodus</div></div></section>
<section class="workspace"><div class="market-card glass" id="squad"><div class="row"><h2>Startelf</h2><span class="small" id="formationLabel">Spieler anklicken für Details</span></div><div class="pitch"><div class="formation" id="lineup"></div></div></div>
<div class="right"><div class="control glass gold clickable" id="matchdaySection" onclick="navigate('matchday')"><div class="row"><div><div class="label">Heute wichtig</div><h2 style="margin:4px 0 0">Spieltagscheck</h2></div><span class="locked" id="alertCount">0 Hinweise</span></div><div id="alerts"><div class="recommend"><div><b>Kader wird geprüft</b><div class="small">Startelf- und Verletzungsdaten laden</div></div><i class="signal"></i></div></div></div><div class="control glass clickable" onclick="navigate('matchday')"><div class="row"><div><div class="label">Nächster Spieltag</div><h2 style="margin:4px 0 0" id="matchday">Wird geladen</h2></div><span class="locked">LIVE</span></div><div class="small">Die Startelf bleibt bei allen Trading-Entscheidungen geschützt.</div></div><div class="control glass"><div class="row"><div><div class="label">Trading-Automatik</div><h2 style="margin:4px 0 0">Sicher gesperrt</h2></div><span class="locked">TEST</span></div><div class="hint">Echte Transfers werden erst nach dem kontrollierten Funktionstest freigegeben.</div><button onclick="toggleTrading()">Automatik prüfen</button></div>
<div class="control glass" id="rules"><h2>Handelsregeln</h2><div class="setting"><label class="label">Mindestreserve</label><select id="cash"><option value="500000">500.000 €</option><option value="1000000">1 Mio. €</option><option value="0">0 €</option></select></div><div class="setting"><label class="label">Maximaler Aufpreis (%)</label><input id="overpay" type="number" min="0" max="30" value="8"></div><button onclick="save()">Änderungen speichern</button></div>
<div class="control glass"><h2>Trading-Fokus</h2><div class="recommend"><div><b>Marktwertplus suchen</b><div class="small">Steigende Spieler priorisieren</div></div><i class="signal"></i></div><div class="recommend"><div><b>Kontostand sichern</b><div class="small">Reserve niemals unterschreiten</div></div><i class="signal"></i></div><button onclick="location.href='/api/export'">Daten für ChatGPT exportieren</button></div></div></section><section class="market-card glass market-wide" id="marketSection"><div class="pagehead"><div><h2 style="margin-bottom:3px">Transfermarkt & Empfehlungen</h2><span class="small" id="marketCount">Live aus KICKBASE</span></div><div class="toolbar"><input id="search" aria-label="Spieler suchen" placeholder="Spieler suchen …" style="width:190px;margin:0" oninput="renderMarket()"><button class="chip active" data-filter="0">Alle</button><button class="chip" data-filter="1">TOR</button><button class="chip" data-filter="2">ABW</button><button class="chip" data-filter="3">MIT</button><button class="chip" data-filter="4">STU</button></div></div><div class="tablewrap"><table><thead><tr><th>SPIELER</th><th>POS.</th><th>MARKTWERT</th><th>PREIS</th><th>TREND</th><th>STATUS</th><th>SIGNAL</th></tr></thead><tbody id="market"></tbody></table></div></section></main></div>
<div class="modal" id="playerModal" onclick="if(event.target===this)closePlayer()"><div class="dialog glass"><button class="close" onclick="closePlayer()" aria-label="Schließen">×</button><div class="label">Spieler-Details</div><div style="display:flex;align-items:center;gap:16px;margin:8px 0 12px"><div id="detailPhotoBox" style="width:88px;height:88px;border-radius:22px;background:linear-gradient(135deg,#dce7dd,#b9cdbd);display:grid;place-items:center;overflow:hidden;position:relative;color:#51705e;font-weight:750"><span id="detailInitials">–</span><img id="detailPhoto" alt="" style="position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:center bottom" onerror="this.style.display='none'"></div><div><h2 id="detailName" style="font-size:28px;margin:5px 0"></h2><span class="pos" id="detailPos"></span></div></div><div class="detailgrid"><div class="detailbox"><div class="label">Marktwert</div><b id="detailValue"></b></div><div class="detailbox"><div class="label">Preis</div><b id="detailPrice"></b></div><div class="detailbox"><div class="label">Trend</div><b id="detailTrend"></b></div><div class="detailbox"><div class="label">Empfehlung</div><b id="detailSignal"></b></div></div><button id="targetButton" onclick="toggleTarget()">Als Ziel markieren</button></div></div><div class="toast" id="toast">Gespeichert</div>
<script>
const euro=n=>new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(n||0);
const pos={1:'TOR',2:'ABW',3:'MIT',4:'STU'},status={2:['Fit','up'],4:['Fraglich','neutral'],5:['Fällt aus','down']};
let appState={players:[],config:{}},filterPos=0,selected=null;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const walk=(v,out=[])=>{if(Array.isArray(v)){for(const x of v)walk(x,out)}else if(v&&typeof v==='object'){out.push(v);for(const x of Object.values(v))walk(x,out)}return out};
function findNum(root,keys){for(const x of walk(root)){for(const k of keys)if(typeof x[k]==='number')return x[k]}return null}
function playerArray(root){if(!root)return[];for(const x of walk(root)){for(const k of ['players','it','pl','lineup'])if(Array.isArray(x[k])&&x[k].length>=7&&x[k].some(p=>p&&typeof p==='object'&&(p.n||p.name)))return x[k]}return[]}
function getSquad(d){const s=d.raw?.sections||{};return playerArray(s.lineup).length?playerArray(s.lineup):playerArray(s.me)}
function idOf(p){return String(p.i||p.id||p.pi||`${p.fn||''}-${p.n||p.name||''}`)}
function initials(p){return `${p.fn||''} ${p.n||p.name||''}`.trim().split(/\s+/).map(x=>x[0]).slice(0,2).join('').toUpperCase()||'–'}
function photoUrl(p){if(!p?.pim)return'';if(/^https?:\/\//i.test(p.pim))return p.pim;return 'https://kickbase.b-cdn.net/'+String(p.pim).replace(/^\/+/, '')}
function photoMarkup(p,size=46){const src=photoUrl(p),name=`${p.fn||''} ${p.n||p.name||''}`.trim();return `<span style="width:${size}px;height:${size}px;border-radius:${size>50?22:14}px;background:linear-gradient(135deg,#dce7dd,#b9cdbd);display:grid;place-items:center;overflow:hidden;color:#51705e;font-weight:750;flex:0 0 auto;position:relative"><span>${esc(initials(p))}</span>${src?`<img src="${esc(src)}" alt="Foto von ${esc(name)}" loading="lazy" style="position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:center bottom" onerror="this.style.display='none'">`:''}</span>`}
function recommendation(p){const rising=p.mvt==2,premium=p.mv?((p.prc-p.mv)/p.mv*100):0;if(p.prob==5)return['Nicht kaufen','down'];if(rising&&premium<=Number(appState.config.maximum_overpay_percent||8))return['Prüfen','up'];return['Beobachten','neutral']}
function renderMarket(){const q=(search.value||'').trim().toLowerCase();const rows=(appState.players||[]).filter(p=>(!filterPos||Number(p.pos)===filterPos)&&(`${p.fn||''} ${p.n||p.name||''}`.toLowerCase().includes(q))).sort((a,b)=>(b.mv||0)-(a.mv||0));market.innerHTML=rows.length?rows.map(p=>{const s=status[p.prob]||['Unbekannt','neutral'],r=p.mvt==2,rec=recommendation(p),name=`${p.fn||''} ${p.n||p.name||''}`.trim();return `<tr class="clickable" data-player="${esc(idOf(p))}"><td class="player"><div style="display:flex;align-items:center;gap:11px">${photoMarkup(p)}<span>${esc(name)}</span></div></td><td><span class="pos">${pos[p.pos]||'–'}</span></td><td>${euro(p.mv)}</td><td>${euro(p.prc)}</td><td class="${r?'up':p.mvt==1?'down':'neutral'}">${r?'↗ steigend':p.mvt==1?'↘ fallend':'→ stabil'}</td><td><span class="pill ${s[1]}">${s[0]}</span></td><td class="${rec[1]}"><b>${rec[0]}</b></td></tr>`}).join(''):'<tr><td colspan="7" class="empty">Keine passenden Spieler gefunden.</td></tr>';document.querySelectorAll('[data-player]').forEach(el=>el.onclick=()=>openPlayer(el.dataset.player))}
function renderLineup(d){const lp=getSquad(d).slice(0,11),places=[2,6,10,2,5,8,11,3,6,9,6],rows=[1,1,1,2,2,2,2,3,3,3,4];const display=lp.length?lp:Array.from({length:11},(_,i)=>({n:'Freier Platz',pos:i===10?1:i<3?4:i<7?3:2}));lineup.innerHTML=display.map((p,i)=>`<button class="slot ${lp.length?'clickable':'empty-slot'}" style="grid-column:${places[i]};grid-row:${rows[i]};border:0;color:var(--ink);margin:auto;padding:4px 5px 7px;overflow:hidden" ${lp.length?`data-squad="${esc(idOf(p))}"`:''}>${lp.length?`<div style="height:43px;margin:-4px -5px 3px;background:linear-gradient(180deg,#e7eee7,#d3e0d4);display:flex;justify-content:center;align-items:flex-end"><img src="${esc(photoUrl(p))}" alt="" style="height:49px;max-width:74px;object-fit:contain;object-position:center bottom" onerror="this.style.display='none'"></div>`:''}<b>${esc(`${p.fn||''} ${p.n||p.name||''}`.trim())}</b><span class="small">${pos[p.pos]||''}</span></button>`).join('');document.querySelectorAll('[data-squad]').forEach(el=>el.onclick=()=>openPlayer(el.dataset.squad,true));formationLabel.textContent=lp.length?'Spieler anklicken für Details':'Kaderdaten werden beim nächsten Sync geladen'}
async function load(){try{const d=await fetch('/api/state').then(r=>r.json());appState=d;const updated=d.updated_at?new Date(d.updated_at).toLocaleString('de-DE',{hour:'2-digit',minute:'2-digit'}):'noch kein Sync';subtitle.textContent=d.league+' · aktualisiert '+updated;marketCount.textContent=d.players.length+' Spieler · Live aus KICKBASE';cash.value=d.config.minimum_cash;overpay.value=d.config.maximum_overpay_percent;const b=findNum(d.raw||{},['budget','b','cash','bal']),sv=findNum(d.raw||{},['teamValue','squadValue','tv']);budget.textContent=b===null?'nach nächstem Sync':euro(b);squadValue.textContent=sv===null?'nach nächstem Sync':euro(sv);offers.textContent=d.players.filter(p=>p.ofc>0).length;renderLineup(d);renderMarket()}catch(e){subtitle.textContent='Verbindung wird erneut versucht …'}}
function navigate(where){const targets={overview:'overview',market:'marketSection',squad:'squad',matchday:'matchdaySection',rules:'rules'};document.getElementById(targets[where]||'overview').scrollIntoView({behavior:'smooth',block:'start'});document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===where))}
function openPlayer(id,squad=false){const pool=squad?getSquad(appState):appState.players;selected=pool.find(p=>idOf(p)===String(id))||appState.players.find(p=>idOf(p)===String(id));if(!selected)return;const rec=recommendation(selected),src=photoUrl(selected);detailName.textContent=`${selected.fn||''} ${selected.n||selected.name||''}`.trim();detailPos.textContent=pos[selected.pos]||'Spieler';detailValue.textContent=euro(selected.mv);detailPrice.textContent=euro(selected.prc||selected.mv);detailTrend.textContent=selected.mvt==2?'↗ steigend':selected.mvt==1?'↘ fallend':'→ stabil';detailSignal.textContent=rec[0];detailInitials.textContent=initials(selected);detailPhoto.style.display=src?'block':'none';detailPhoto.src=src;detailPhoto.alt=src?'Foto von '+detailName.textContent:'';updateTargetButton();playerModal.classList.add('open')}
function closePlayer(){playerModal.classList.remove('open');selected=null}
function updateTargetButton(){const ids=(appState.config.targets||[]).map(String),on=selected&&ids.includes(idOf(selected));targetButton.textContent=on?'Von Zielliste entfernen':'Als Ziel markieren'}
async function toggleTarget(){if(!selected)return;let ids=(appState.config.targets||[]).map(String),id=idOf(selected);ids=ids.includes(id)?ids.filter(x=>x!==id):[...ids,id];await saveConfig({targets:ids});appState.config.targets=ids;updateTargetButton();toastMsg('Zielliste gespeichert')}
async function saveConfig(payload){return fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})}
async function save(){const r=await saveConfig({minimum_cash:Number(cash.value),maximum_overpay_percent:Number(overpay.value)});if(r.ok){appState.config.minimum_cash=Number(cash.value);appState.config.maximum_overpay_percent=Number(overpay.value);renderMarket();toastMsg('Handelsregeln gespeichert')}}
function toastMsg(t){toast.textContent=t;toast.style.opacity=1;toast.style.transform='translateY(0)';setTimeout(()=>{toast.style.opacity=0;toast.style.transform='translateY(15px)'},1800)}
function toggleTrading(){alert('Sicherheitscheck: Die Automatik bleibt im Testmodus. Es werden noch keine echten Käufe oder Verkäufe ausgelöst.')}
document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>navigate(b.dataset.view));document.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{filterPos=Number(b.dataset.filter);document.querySelectorAll('.chip').forEach(x=>x.classList.toggle('active',x===b));renderMarket()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closePlayer()});load();setInterval(load,60000);
</script></body></html>'''

PAGE = (ROOT / "dashboard.html").read_text(encoding="utf-8")


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.get("/api/state")
def state():
    market_file = DATA / "state.json"
    if not market_file.exists():
        market_file = DATA / "letzter_markt.json"
    snapshot = json.loads(market_file.read_text(encoding="utf-8")) if market_file.exists() else {"market": {"it": []}, "league": "Bierbanausen", "updated_at": None}
    config = read_config()
    strategy = json.loads(STRATEGY.read_text(encoding="utf-8")) if STRATEGY.exists() else {}
    trade_log = DATA / "handelslog.json"
    try:
        trades = json.loads(trade_log.read_text(encoding="utf-8"))[-30:] if trade_log.exists() else []
    except (OSError, ValueError, TypeError):
        trades = []
    return jsonify({"league": snapshot.get("league"), "updated_at": snapshot.get("updated_at"), "players": snapshot.get("players") or (snapshot.get("market", {}).get("it", []) if isinstance(snapshot.get("market"), dict) else []), "config": config, "strategy": strategy, "trades": trades, "raw": snapshot})


@app.get("/api/export")
def export_data():
    market_file = DATA / "state.json"
    if not market_file.exists():
        market_file = DATA / "letzter_markt.json"
    snapshot = json.loads(market_file.read_text(encoding="utf-8")) if market_file.exists() else {}
    config = read_config()
    strategy = json.loads(STRATEGY.read_text(encoding="utf-8")) if STRATEGY.exists() else {}
    export = {
        "notice": "Enthält keine KICKBASE-Zugangsdaten.",
        "market_snapshot": snapshot,
        "settings": config,
        "strategy": strategy
    }
    content = json.dumps(export, ensure_ascii=False, indent=2)
    return Response(content, mimetype="application/json", headers={
        "Content-Disposition": "attachment; filename=kickbase_export.json"
    })


@app.post("/api/config")
def update_config():
    config = read_config()
    incoming = request.get_json(force=True)
    if "minimum_cash" in incoming:
        config["minimum_cash"] = max(0, int(incoming["minimum_cash"]))
    if "maximum_overpay_percent" in incoming:
        config["maximum_overpay_percent"] = min(30, max(0, int(incoming["maximum_overpay_percent"])))
    if "targets" in incoming and isinstance(incoming["targets"], list):
        config["targets"] = [str(item)[:120] for item in incoming["targets"][:100]]
    if "watchlist_names" in incoming and isinstance(incoming["watchlist_names"], list):
        clean = []
        for item in incoming["watchlist_names"][:100]:
            name = " ".join(str(item).strip().split())[:100]
            if name and name.casefold() not in {value.casefold() for value in clean}:
                clean.append(name)
        config["watchlist_names"] = clean
    numeric_limits = {
        "minimum_squad_size": (11, 30),
        "max_actions_per_run": (1, 5),
        "portfolio_actions_per_run": (1, 5),
        "matchday_protection_hours": (0, 120),
        "bid_window_minutes": (5, 30),
        "minimum_starting_probability": (1, 5),
        "asking_price_percent": (-10, 30),
        "minimum_offer_percent": (70, 120),
        "rising_price_bonus_percent": (0, 20),
        "falling_price_discount_percent": (0, 20),
        "safe_s11_price_bonus_percent": (0, 20),
        "target_profit_percent": (0, 50),
        "star_listing_bonus_percent": (0, 50),
        "star_sale_profit_percent": (0, 100),
    }
    for key, (low, high) in numeric_limits.items():
        if key in incoming:
            config[key] = min(high, max(low, int(incoming[key])))
    for key in ("auto_buy", "auto_instant_sell", "auto_accept_offers", "auto_adjust_listings", "ligainsider_enabled", "portfolio_mode", "list_all_players", "kickbest_enabled"):
        if key in incoming:
            config[key] = bool(incoming[key])
    CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return jsonify({"ok": True})


@app.post("/api/trading")
def trading_mode():
    config = read_config()
    incoming = request.get_json(force=True)
    enabled = bool(incoming.get("enabled"))
    if enabled and incoming.get("confirmation") != "ECHT HANDELN":
        return jsonify({"ok": False, "error": "Bestätigung fehlt."}), 400
    config["trading_enabled"] = enabled
    config["mode"] = "live" if enabled else "observe"
    CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return jsonify({"ok": True, "enabled": enabled})


def serve():
    from waitress import serve as waitress_serve
    waitress_serve(app, host="127.0.0.1", port=8765, threads=4)


if __name__ == "__main__":
    serve()