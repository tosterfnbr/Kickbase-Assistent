/* Strategy UI: explanations, configurable rules and clearly separated trials. */
(() => {
 const nav=document.querySelector('.nav');
 nav.insertAdjacentHTML('beforeend','<button data-page="planner">◎ Strategie & Deals</button>');
 nav.querySelector('[data-page="planner"]').onclick=()=>showPage('planner');
 document.head.insertAdjacentHTML('beforeend',`<style>
 .planner-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.planner-box{padding:20px;min-width:0}.planner-box h3{margin:0 0 12px}.planner-wide{grid-column:1/-1}.planner-box table{min-width:680px}.planner-box .scroll{overflow:auto;max-height:480px}.planner-box td{vertical-align:top;max-width:330px}.planner-box small{display:block;line-height:1.5}.planner-settings{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.planner-settings label{display:block;font-size:13px}.planner-settings input,.planner-settings select{width:100%;margin:5px 0 10px;padding:9px;border:1px solid #ccd7d0;border-radius:8px}.planner-note{padding:12px;background:#f0f5f1;border-radius:10px;margin:10px 0}.planner-box ul{padding-left:20px}.planner-box li{margin:7px 0}.dialog{max-height:90vh;overflow:auto}#decisionDetail{margin:12px 0;font-size:13px}#decisionDetail p{margin:8px 0}@media(max-width:800px){.planner-grid,.planner-settings{grid-template-columns:1fr}.planner-wide{grid-column:auto}}
 </style>`);
 document.querySelector('main').insertAdjacentHTML('beforeend',`<section class="page" id="page-planner">
 <div class="page-title"><div><h2>Strategie & Deals</h2><div class="meta" id="plannerVersion">Wartet auf Daten</div></div></div>
 <div class="planner-grid">
 <article class="panel planner-box planner-wide"><h3>Wann gibt der Assistent Gebote ab?</h3><div id="bidTiming"></div><div id="dealCriteria"></div></article>
 <article class="panel planner-box"><h3>Beste gefundene Kaufkombination</h3><div id="basketSummary"></div><div id="basketAlternatives"></div></article>
 <article class="panel planner-box"><h3>Spieltags- und Liga-Prüfung</h3><div id="leagueChecks"></div><div id="capitalPlan"></div></article>
 <article class="panel planner-box planner-wide"><h3>Warum dieser Deal?</h3><div class="meta">Kandidaten sind noch keine zugesicherten Käufe. Eine passende Kombination muss ins Budget und in den Kader passen.</div><div class="scroll"><table><thead><tr><th>Spieler / Entscheidung</th><th>Form & Einsatz</th><th>Prognose / Gegner</th><th>Preisgrenze / Datenalter</th></tr></thead><tbody id="dealRows"></tbody></table></div></article>
 <article class="panel planner-box planner-wide"><h3>Kaufgrund & Verkaufsplan</h3><div class="scroll"><table><thead><tr><th>Spieler / Rolle</th><th>Warum gekauft?</th><th>Kosten / Ergebnis</th><th>Verkaufsregel</th></tr></thead><tbody id="holdingRows"></tbody></table></div><small>Ein negativer Marktwertunterschied ist noch kein realisierter Verlust. Grenzen garantieren keinen Käufer.</small></article>
 <article class="panel planner-box"><h3>Ersatz vor Verkauf</h3><div id="replacementRows"></div></article>
 <article class="panel planner-box"><h3>Ergebnisse seit Aufzeichnungsbeginn</h3><div id="resultsSummary"></div><div id="changeRows"></div></article>
 <article class="panel planner-box planner-wide"><h3>Probelauf: Regeln vergleichen</h3><div id="trialSummary"></div><div class="planner-settings"><label>Reserve im Probelauf (€)<input id="trial_minimum_cash" type="number" min="0" max="100000000"></label><label>Mindest-S11 im Probelauf<input id="trial_min_s11" type="number" min="1" max="5"></label></div><div class="scroll"><table><thead><tr><th>Variante / Datum</th><th>Hypothetischer Einsatz</th><th>Marktwertänderung</th><th>Letzte Bewertung</th></tr></thead><tbody id="trialRows"></tbody></table></div></article>
 <article class="panel planner-box planner-wide"><h3>Strategie einstellen</h3><div class="planner-settings" id="strategyFields"></div>
 <label>Verkaufsentscheidung nach<select id="sale_price_basis"><option value="market">Aktuellem Marktwert – alter Einkaufspreis blockiert keinen Verkauf</option><option value="purchase">Einkaufspreis – Einstand bei Zielgrenzen berücksichtigen</option></select></label><small>Realisierte Gewinne und Verluste werden in beiden Modi gegenüber dem tatsächlichen Einkaufspreis berechnet.</small>
 <h3>Ligavorgaben</h3><div class="planner-settings">
 <label>MVP-Verkaufsregel<select id="mvp_rule_enabled"><option value="true">Aktiv</option><option value="false">Aus</option></select></label>
 <label>Endgültiger Spieltags-MVP<select id="mvpPlayer"><option value="">Noch unbekannt</option></select></label>
 <label>Spieltag<input id="mvpDay" type="number" min="1" max="40"></label>
 <label>Spieltag vollständig beendet am<input id="mvpEnded" type="datetime-local"></label>
 <label>Quelle / Bestätigung<input id="mvpSource" placeholder="z. B. KICKBASE-Spieltagsergebnis"></label>
 <label>Ergebnis endgültig bestätigt<select id="mvpConfirmed"><option value="false">Noch nicht bestätigt</option><option value="true">Ja, geprüft</option></select></label>
 <label>MVP-Verkauf erledigt<select id="mvpCompleted"><option value="false">Noch offen</option><option value="true">Verkauf an KICKBASE selbst geprüft</option></select></label>
 <label>Winterreset berücksichtigen<select id="winter_reset_enabled"><option value="false">Aus</option><option value="true">Aktiv</option></select></label>
 <label>Vereinbarter Reset-Termin<input id="winter_reset_at" type="datetime-local"></label></div>
 <small>Kein automatisches Raten des MVP oder Reset-Datums. Ein bestätigter eigener MVP wird als Verkauf an KICKBASE vorgemerkt; Managerangebote werden für ihn nicht angenommen.</small>
 <button class="primary" id="saveStrategy">Strategie und Proberegeln speichern</button><div class="meta" id="strategySaveStatus"></div>
 </article>
 <article class="panel planner-box planner-wide"><h3>Zusätzliche Pflichtspiele</h3><p>Für Pokal und internationale Spiele können bestätigte Termine ergänzt werden. Sie fließen in die Belastungswarnung ein. Ohne Eintrag ist diese Belastung unbekannt.</p>
 <div class="planner-settings"><label>Verein<select id="fixtureTeam"></select></label><label>Anpfiff<input id="fixtureDate" type="datetime-local"></label><label>Quelle<input id="fixtureSource" placeholder="Quelle des bestätigten Spielplans"></label></div><button class="primary" id="addFixture">Termin ergänzen</button><div id="fixtureRows"></div></article>
 </div></section>`);
 const fields=[
 ['combination_size','Maximal gemeinsam geprüfte Käufe',3,1,3],['bench_size','Günstige Reservepositionen',2,0,4],
 ['bench_player_budget','Preisgrenze pro Bankspieler (€)',4000000,500000,20000000],['maximum_squad_size','Maximale Kadergröße',18,11,30],
 ['maximum_per_club','Maximal Spieler pro Verein',3,1,18],['euros_per_extra_point','Zusätzliche Preisgrenze je geschätztem Mehrpunkt (€)',30000,0,200000],
 ['bid_switch_min_gain','Mindest-Mehrpunkte für Gebotswechsel',10,1,100],['trading_take_profit_percent','Trading-Kursziel (%)',8,1,50],
 ['trading_stop_loss_percent','Trading-Verlustgrenze (%)',5,1,30],['trading_max_hold_days','Trading-Haltedauer (Tage)',7,1,30],
 ['slow_seller_days','Preisprüfung nach Tagen ohne Verkauf',3,1,14]
 ];
 $('strategyFields').innerHTML=fields.map(([id,label,v,min,max])=>`<label>${esc(label)}<input id="${id}" type="number" min="${min}" max="${max}" value="${v}"></label>`).join('');
 let initialized=false;
 const money=v=>v==null?'unbekannt':euro(v),fmt=v=>v==null?'unbekannt':Number(v).toLocaleString('de-DE',{maximumFractionDigits:1});
 const date=v=>v?new Date(typeof v==='number'?v*1000:v).toLocaleString('de-DE'):'unbekannt';
 const localDate=v=>{if(!v)return'';const d=new Date(v);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)};
 const role=v=>({trading:'Trading',startelf:'Startelf',bench:'Bank'})[v]||'Unbekannt';
 const list=items=>'<ul>'+items.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>';
 function timing(c,t){
  const updated=Date.parse(state.updated_at||''),next=Number.isFinite(updated)?date(updated/1000+Math.max(5,Number(c.poll_minutes||5))*60):'nach erstem Sync';
  return `<div class="planner-note"><b>${c.trading_enabled&&c.mode==='live'?'Echter Handel aktiviert':'Testmodus – keine echten Gebote'}</b><p>Prüfung etwa alle ${Math.max(5,Number(c.poll_minutes||5))} Minuten. Nächster regulärer Check ungefähr ${esc(next)}; Verzögerungen bei Abrufen sind möglich.</p><p>${c.continuous_bidding!==false?'Gebote während der gesamten Angebotszeit erlaubt.':'Neue Gebote nur in den letzten '+Number(c.bid_window_minutes||10)+' Minuten vor Angebotsende.'} ${c.auto_buy===false?'Neue Käufe sind ausgeschaltet.':''} Identische offene Gebote werden nicht erneut gesendet. Nach einer Rücknahme wartet neues Bieten auf einen frischen Datenstand.</p><small>${Number(c.portfolio_actions_per_run||c.max_actions_per_run||3)} Aktionen je Durchlauf; Rücknahmen und Verkäufe können Vorrang haben. Der PC und der Assistent müssen laufen.</small></div>`;
 }
 function render(){
  if(!state?.config)return;
  const c=state.config,t=state.raw?.trading||{},j=t.journal||{},basket=t.combination,checks=t.league_checks||{};
  $('plannerVersion').textContent='Version '+(state.raw?.version||'noch kein Sync')+' · Prognosen sind Schätzungen';
  if(state.raw&&Object.prototype.hasOwnProperty.call(state.raw,'account_budget'))$('budget').textContent=money(state.raw.account_budget);
  $('bidTiming').innerHTML=timing(c,t);
  $('dealCriteria').innerHTML=list([
   `Startelf: S11 mindestens ${c.minimum_starting_probability||3}/5, mindestens 2 Saisoneinsätze, Saison-Ø mindestens 45 Minuten und 50 Punkte. Bei vollständigen letzten 3 Spielen auch Ø mindestens 45 Minuten und gewichtete aktuelle Form mindestens 50 Punkte.`,
   `Trading: positiver 24h-Trend, KI-Trend mindestens 0, kein Gamble-Signal, Preis höchstens ${money(c.max_trading_player_price||3000000)}. Zwei Tage linear fortgeschriebener 24h-Trend abzüglich Aufpreis: mindestens ${money(c.minimum_trading_gain||100000)} Potenzial. Keine Gewinnzusage.`,
   `Alle Käufe: Verfügbarkeit und Risikomeldungen, vorhandene Gebote, Reserve, Kader- und Vereinsgrenzen prüfen. Preis mindestens Marktwert; Obergrenze höchstens ${c.maximum_overpay_percent??8}% Aufpreis und nicht über positivem Base-XI Fair Value. Mehrpunkte und vergleichbare Alternativen können die Grenze weiter senken.`,
   'Trading-Budget: erst bei vollständiger Elf; maximal 20% nach Reserve, bei fehlender Bank nur 10%, zusätzlich absolute Trading-Grenze. Vor einem nahen Winterreset keine neuen Trading-Käufe.'
  ]);
  $('basketSummary').innerHTML=basket?`<b>${esc(basket.target.formation)} · ${basket.target.filled}/11 Positionen</b><p>Käufe: ${basket.ids.map(id=>esc(name(state.players.find(p=>pid(p)===id)||{n:id}))).join(', ')||'Kein zusätzlicher Kauf nötig / bezahlbar'}</p><p>Einsatz ${money(basket.cost)} · geschätzte Mehrpunkte ${fmt(basket.gain)}</p><small>${basket.evaluated} Kombinationen aus ${basket.shortlist_size} Kandidaten geprüft. ${esc(basket.notice)}</small>`:'Kein Kaufplan verfügbar; aktuelle Blockiergründe im Live-Feed prüfen.';
  $('basketAlternatives').innerHTML=basket?list(basket.alternatives.slice(1,4).map(a=>a.players.map(p=>p.name).join(' + ')+' · '+money(a.cost)+' · '+a.filled+'/11 · geschätzt '+fmt(a.expected_points)+' Pkt.')):'';
  $('leagueChecks').innerHTML=list(checks.checks||['Prüfung folgt beim nächsten Sync']);
  const capital=t.capital||{};
  $('capitalPlan').innerHTML=`<div class="planner-note">Kontostand ${money(capital.budget)}<br>Offene Gebote ${money(capital.open_bids)}<br>Verfügbar nach Reserve ${money(capital.free)}<br>Trading-Grenze ${money(capital.trading_limit)}</div>`;
  const planned=new Set((t.planned||[]).filter(x=>x.action==='buy').map(x=>x.player_id));
  $('dealRows').innerHTML=(state.players||[]).map(p=>{
   const a=p.analysis||{},r=t.scouting?.[pid(p)]||{},ages=a.ages_hours||{},b=p.base_xi||{};
   return `<tr data-deal="${esc(pid(p))}"><td><b>${esc(name(p)||p.ln)}</b><small>${esc(role(r.purpose))} · ${planned.has(pid(p))?'Gebot im aktuellen Plan':r.eligible?'Geeignet, derzeit kein neues Gebot geplant':'Nicht zum Kauf freigegeben'}</small><small>${esc(r.reason||'Eigener Kader / keine Bewertung')}</small></td><td>Letzte Spiele: ${fmt(a.recent_points)} gewichtete Pkt.<br>Letzte 3: ${fmt(a.recent_minutes)} Min. Ø<small>Saisonstarts: ${fmt(b.starts)} · S11 ${s11(p)??'?'}/5</small>${(a.rows||[]).map(x=>`<small>ST ${x.day}: ${fmt(x.minutes)} Min. / ${fmt(x.points)} Pkt.</small>`).join('')}</td><td>Geschätzt ${fmt(a.expected_points)} Pkt.<small>${esc((a.risks||[]).join('; ')||'Kein erkannter Risikohinweis')}</small><small>Gegner nächste 3: ${(a.opponents||[]).map(x=>esc(x.id||'?')).join(', ')||'unbekannt'}</small><small>Gegnerfaktor ${fmt(a.opponent_factor)} · ${esc(a.opponent_basis||'unbekannt')}</small></td><td>Gebot ${money(r.amount)}<br>Obergrenze ${money(r.ceiling)}<small>Alter in Stunden: Markt ${fmt(ages.market)} / S11 ${fmt(ages.s11)} / Base-XI ${fmt(ages.base_xi)} / Minuten ${fmt(ages.minutes)}</small><small>Vertrauen: ${esc(a.confidence||'gering')}</small></td></tr>`;
  }).join('')||'<tr><td colspan="4">Noch keine Marktspieler.</td></tr>';
  $('dealRows').querySelectorAll('[data-deal]').forEach(el=>el.onclick=()=>openPlayer(el.dataset.deal));
  $('holdingRows').innerHTML=(j.holdings||[]).map(h=>{
   const ex=(t.exits||[]).find(x=>x.player_id===h.id)||{};
   return `<tr><td><b>${esc(h.name)}</b><select data-role="${esc(h.id)}"><option value="">Automatisch / unbekannt</option>${['startelf','trading','bench'].map(v=>`<option value="${v}" ${h.purpose===v?'selected':''}>${role(v)}</option>`).join('')}</select></td><td>${esc(h.purchase_reason)}<small>Gekauft: ${date(h.acquired_at)} · damalige Preisgrenze ${money(h.price_ceiling)}</small></td><td>Kaufpreis ${money(h.cost)}<small>Unrealisiert ${money(h.unrealized_profit)}</small><small>${fmt(h.points_since_observation)} Punkte seit erster Beobachtung</small></td><td>Ziel ${money(ex.goal)}<br>Rückgangsauslöser ${money(ex.stop_floor)}<small>Bezugswert: ${money(ex.reference_value)} · ${esc(ex.reference_basis)}</small><small>Frist ${date(ex.deadline)}</small><small>${esc((ex.reasons||[]).join('; ')||'Kein Ausstieg ausgelöst')}</small></td></tr>`;
  }).join('')||'<tr><td colspan="4">Aufzeichnung beginnt beim nächsten Kader-Sync.</td></tr>';
  $('holdingRows').querySelectorAll('[data-role]').forEach(el=>el.onchange=async()=>{
   const roles={...(state.config.player_roles||{})};if(el.value)roles[el.dataset.role]=el.value;else delete roles[el.dataset.role];
   const r=await postConfig({player_roles:roles});if(r.ok){state.config.player_roles=roles;toastMsg('Rolle gespeichert; wirksam beim nächsten Sync')}else toastMsg('Speichern fehlgeschlagen');
  });
  $('replacementRows').innerHTML=(t.replacements||[]).map(x=>`<div class="planner-note"><b>${esc(x.name)}</b> · Verkaufsgrenze ${money(x.sale_floor)}<small>${x.secured?'Vollständige Elf bleibt mit vorhandenen Spielern erhalten':'Ersatz erst tatsächlich kaufen; Verkauf noch nicht abgesichert'}</small>${(x.alternatives||[]).map(a=>`<small>${esc(a.name)} · ${money(a.price)} · ${a.affordable_now?'jetzt finanzierbar':'Budget fehlt noch'}</small>`).join('')}</div>`).join('')||'Noch keine Kaderprüfung.';
  $('resultsSummary').innerHTML=`<b>${money(j.realized_profit)} erfasster realisierter Gewinn/Verlust</b><p>${j.confirmed_trades||0} bestätigte Verkäufe mit bekanntem Einstand · ${j.unknown_results||0} Ergebnisse mit unbekanntem Erlös/Einstand</p>${list(Object.entries(j.groups||{}).map(([k,v])=>role(k)+': '+v.trades+' Verkäufe, '+money(v.profit)))}<small>${esc(j.notice||'Noch keine Historie')}</small>`;
  $('changeRows').innerHTML='<h4>Änderungen seit vorherigen Prüfungen</h4>'+list((j.changes||[]).slice(-8).reverse().map(x=>x.name+' · '+({s11:'S11',minutes:'Minuten',status:'Status',market_value:'Marktwert'})[x.field]+': '+x.before+' → '+x.after+' · '+date(x.time)));
  const trial=t.trial||{};
  $('trialSummary').textContent=trial.notice||'Probelauf wird mit dem nächsten verfügbaren Kaufplan aufgezeichnet. Er führt keine Aufträge aus.';
  $('trialRows').innerHTML=(trial.rows||[]).slice().reverse().map(x=>`<tr><td>${esc(x.variant)}<small>${date(x.created_at)}</small></td><td>${money(x.cost)}</td><td>${money(x.hypothetical_change)}<small>hypothetisch, nicht realisiert</small></td><td>${date(x.marked_at)}</td></tr>`).join('');
  if(!initialized&&state.updated_at){
   for(const [id,label,v] of fields)$(id).value=c[id]??v;
   $('trial_minimum_cash').value=c.trial_minimum_cash??2000000;$('trial_min_s11').value=c.trial_min_s11??4;
   $('sale_price_basis').value=c.sale_price_basis||'market';
   for(const key of ['mvp_rule_enabled','winter_reset_enabled'])$(key).value=String(c[key]??(key==='mvp_rule_enabled'));
   $('winter_reset_at').value=localDate(c.winter_reset_at);
   const m=c.mvp_confirmation||{};$('mvpDay').value=m.matchday||'';$('mvpSource').value=m.source||'';$('mvpEnded').value=localDate(m.ended_at);$('mvpConfirmed').value=String(m.confirmed===true);
   $('mvpCompleted').value=String(m.completed===true);
   $('mvpPlayer').innerHTML='<option value="">Noch unbekannt</option><option value="other">Gehört einem anderen Manager</option>'+squad().map(p=>`<option value="${esc(pid(p))}">${esc(name(p))}</option>`).join('');$('mvpPlayer').value=m.player_id||'';
   initialized=true;
  }
  const selectedTeam=$('fixtureTeam').value,teams=new Map();[...squad(),...(state.players||[])].forEach(p=>{const b=p.base_xi||{};if(b.team_id)teams.set(b.team_id,b.team_name||b.team_id)});
  $('fixtureTeam').innerHTML=[...teams].map(([id,n])=>`<option value="${esc(id)}">${esc(n)}</option>`).join('');if(selectedTeam)$('fixtureTeam').value=selectedTeam;
  $('fixtureRows').innerHTML=(c.additional_fixtures||[]).map((x,i)=>`<div class="planner-note">${esc(teams.get(x.team_id)||x.team_id)} · ${date(x.date)} · ${esc(x.source)} <button data-remove-fixture="${i}">Entfernen</button></div>`).join('');
  $('fixtureRows').querySelectorAll('[data-remove-fixture]').forEach(el=>el.onclick=async()=>{const xs=(state.config.additional_fixtures||[]).filter((x,i)=>i!==Number(el.dataset.removeFixture));const r=await postConfig({additional_fixtures:xs});if(r.ok){state.config.additional_fixtures=xs;render()}});
 }
 $('saveStrategy').onclick=async()=>{
  const values={};for(const [id,label,v,min,max] of fields){const n=Number($(id).value);if(!Number.isFinite(n)||n<min||n>max){toastMsg('Bitte prüfen: '+label);return}values[id]=n;}
  values.trial_minimum_cash=Number($('trial_minimum_cash').value);values.trial_min_s11=Number($('trial_min_s11').value);
  values.sale_price_basis=$('sale_price_basis').value;
  values.mvp_rule_enabled=$('mvp_rule_enabled').value==='true';values.winter_reset_enabled=$('winter_reset_enabled').value==='true';
  values.winter_reset_at=$('winter_reset_at').value?new Date($('winter_reset_at').value).toISOString():null;
  values.mvp_confirmation={player_id:$('mvpPlayer').value,matchday:Number($('mvpDay').value)||null,source:$('mvpSource').value,ended_at:$('mvpEnded').value?new Date($('mvpEnded').value).toISOString():null,confirmed:$('mvpConfirmed').value==='true'};
  values.mvp_confirmation.completed=$('mvpCompleted').value==='true';
  const r=await postConfig(values);if(r.ok){Object.assign(state.config,values);$('strategySaveStatus').textContent='Gespeichert. Der nächste Sync verwendet diese Regeln. Proberegeln verändern keine echten Aufträge.';render()}else{const e=await r.json();$('strategySaveStatus').textContent=e.error||'Speichern fehlgeschlagen'}
 };
 $('addFixture').onclick=async()=>{
  if(!$('fixtureTeam').value||!$('fixtureDate').value||!$('fixtureSource').value.trim()){toastMsg('Verein, Datum und Quelle ausfüllen');return}
  const xs=[...(state.config.additional_fixtures||[]),{team_id:$('fixtureTeam').value,date:new Date($('fixtureDate').value).toISOString(),source:$('fixtureSource').value.trim()}];
  const r=await postConfig({additional_fixtures:xs});if(r.ok){state.config.additional_fixtures=xs;render();toastMsg('Spieltermin gespeichert')}
 };
 const originalOpen=openPlayer;
 openPlayer=id=>{originalOpen(id);if(!selected)return;let box=$('decisionDetail');if(!box){document.querySelector('#playerModal .dialog').insertAdjacentHTML('beforeend','<div id="decisionDetail"></div>');box=$('decisionDetail')}
  const p=selected,a=p.analysis||{},r=state.raw?.trading?.scouting?.[pid(p)]||{},h=(state.raw?.trading?.journal?.holdings||[]).find(x=>x.id===pid(p));
  box.innerHTML=`<h3>Warum dieser Deal?</h3><p>${esc(r.reason||h?.purchase_reason||'Noch keine Entscheidung aufgezeichnet')}</p><p>Rolle: ${esc(role(r.purpose||h?.purpose))} · individuelle Preisgrenze ${money(r.ceiling??h?.price_ceiling)}</p><p>Gewichtete Form ${fmt(a.recent_points)} Pkt. · letzte 3 Spiele ${fmt(a.recent_minutes)} Minuten Ø · erwartete Punkte ${fmt(a.expected_points)} (Schätzung).</p>${list(a.risks||[])}<p>Zusätzliche Spielbelastung: ${esc(typeof a.international_schedule==='string'?a.international_schedule:'Hinterlegte Pflichtspiele berücksichtigt')}</p>`;
 };
 const oldFeed=renderFeed;renderFeed=()=>{oldFeed();render()};
 window.renderPlanner=render;render();setInterval(render,60000);
})();
