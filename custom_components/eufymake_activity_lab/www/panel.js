class EufyMakeActivityLab extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'}); this.filter=''; this.selected=null;
    this.shadowRoot.addEventListener('click', e => this.click(e));
    this.shadowRoot.addEventListener('submit', e => this.submit(e));
    this.shadowRoot.addEventListener('input', e => {
      if (e.target.id === 'bookmarks-only') { this.bookmarksOnly=e.target.checked; this.page=0; this.renderRows(); }
      if (e.target.id === 'filter') { this.filter=e.target.value; this.page=0; this.renderRows(); }
    });
  }
  set hass(value) { this._hass=value; this.start(); }
  set panel(value) { this._panel=value; this.start(); }
  set narrow(value) { this._narrow=value; const m=this.shadowRoot.querySelector('ha-menu-button'); if(m)m.narrow=value; }
  connectedCallback() { this.start(); }
  disconnectedCallback() { clearInterval(this.timer); this.timer=null; }
  start() {
    if(!this._hass || !this._panel || !this.isConnected) return;
    if(!this.timer) { this.refresh(); this.timer=setInterval(()=>this.refresh(),5000); }
  }
  async request(action='read',data={}) {
    return this._hass.callWS({type:'eufymake_activity_lab/action',entry_id:this._panel.config.entry_id,action,data});
  }
  async refresh() {
    if(this.busy)return; this.busy=true;
    try { this.data=await this.request(); if(this.fullEvents){const events=new Map(this.fullEvents.map(e=>[e.id,e]));this.data.events.forEach(e=>events.set(e.id,e));this.fullEvents=Array.from(events.values()).sort((a,b)=>a.time.localeCompare(b.time)).slice(-this.data.limit);this.data.events=this.fullEvents;} this.error=''; if(!this.shadowRoot.activeElement?.matches('input,textarea,select'))this.render(); }
    catch(e) { this.error=e.message || 'Connection unavailable'; this.render(); }
    finally {this.busy=false;}
  }
  esc(x) { return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  time(x) { return x ? new Date(x).toLocaleString(this._hass?.locale?.language||'en-US',{timeZone:'America/Los_Angeles',timeZoneName:'short'}) : 'Not yet received'; }
  pair(e) { return e.kind==='status' ? `${e.state}/${e.step}` : ''; }
  meaning(e) { const p=this.pair(e),l=this.data.labels[p]; return l ? `${l.label} (${l.confidence})` : e.detail || (p ? this.builtinMeaning(e) : this.rawReportMeaning(e)); }
  rawReportMeaning(e) {
    const fields=e.fields||{};
    if(e.command!==1118 && e.command!==1153)return '';
    const bed=e.command===1118,code=fields[bed?'plateType':'attType'];
    const labels=bed?{0:'No bed detected',1:'Standard Flatbed',2:'Mini Flatbed',3:'Rotary'}:{0:'No accessory detected',1:'Mini Flatbed',2:'Standard Flatbed',4:'Rotary'};
    const name=Number.isInteger(code)?labels[code]||'Unknown ('+code+')':'Invalid code';
    return (bed?'Bed report: ':'Accessory report: ')+name+(fields.reply!==undefined&&bed?' · raw reply '+String(fields.reply):'');
  }
  builtinMeaning(e) {
    const labels={'0/0':'Idle','2/1':'Transferring print file','2/2':'Waiting for Start','2/3':'Paused','2/4':'Printing','2/6':'Priming print head','5/3':'Injecting ink','5/7':'Automatic flash clean','5/9':'Automatic moisturizing','5/10':'Automatic deep cleaning','6/1':'Updating firmware','8/0':'Taking snapshot','9/0':'Calibration / self-check','13/0':'Post-moisturizing maintenance (inferred)','13/1':'Post-deep-clean maintenance'};
    return labels[this.pair(e)] || 'Unknown (' + this.pair(e) + ') — Meaning not yet confirmed';
  }
  duration(value) {
    if(typeof value!=='number'||!Number.isFinite(value)||value<0)return '—';
    const n=Math.floor(value),h=Math.floor(n/3600),m=Math.floor(n%3600/60);
    return (h?h+'h ':'')+(m||h?m+'m ':'')+(n%60)+'s';
  }
  decodedSection(d) {
    const decoded=d.decoded||{},hw=decoded.hardware||{},read=decoded.readings||{}, activity=read.activity;
    const fresh=x=>d.connected && x?.time && Date.now()-new Date(x.time).getTime()>=0 && Date.now()-new Date(x.time).getTime()<=120000;
    const latestReport=[hw.bed,hw.accessory].filter(Boolean).sort((a,b)=>String(b.time).localeCompare(String(a.time)))[0];
    const bedWarning=hw.bed_present===false && fresh(latestReport)?'<p role="status" style="color:#b45309;background:#fef3c7;padding:10px;border-radius:8px">Bed not detected. Make sure a bed is installed and its locking latch is fully closed.</p>':'';
    const device=x=>x?`${this.esc(x.label)} · code ${this.esc(x.code)} · command ${this.esc(x.source_command)}${x.reply!==undefined?' · raw reply '+this.esc(x.reply):''} · ${this.esc(this.time(x.time))}`:'Not reported';
    const dims=hw.bed&&fresh(hw.bed)?{1:'335 × 420 mm / 13.19 × 16.54 in',2:'335 × 90 mm / 13.19 × 3.54 in'}[hw.bed.code]:null;
    return `<section><h2>Printer and accessory observations</h2>${bedWarning}<p>Bed: ${device(hw.bed)}${dims?' · '+dims:''}</p><p>Accessory: ${device(hw.accessory)}</p><p>${this.esc(hw.consistency||'Waiting for reports')}. Last reports may be stale; raw sources remain independent.</p><p>Activity: ${this.esc(decoded.status||'Waiting for status')} ${activity?'· '+this.esc(activity.operation)+' progress: '+(fresh(activity)&&activity.progress!==null?this.esc(activity.progress)+'%':'Unavailable / stale'):''}</p></section>`;
  }
  liveSection(d) {
    const esc=x=>this.esc(x), fields=key=>d.live?.[key]?.fields||{}, ink=fields('1100').ink||{}, waste=fields('1100').wasteInk||{};
    const num=x=>typeof x==='number'&&Number.isFinite(x)?x:null;
    const level=x=>num(x)!==null && x>=0 && x<=10000?(x/100).toFixed(1)+'% / '+(x/100).toFixed(1)+' mL':'—';
    const expiry=x=>num(x)!==null?x+' days':'—';
    const active=d.connected && d.current && d.current.state===2 && [3,4].includes(d.current.step);
    const sample=d.decoded?.readings?.['1001'];
    const fresh=active && sample?.time && Date.now()-new Date(sample.time).getTime()>=0 && Date.now()-new Date(sample.time).getTime()<=120000;
    const progress=fresh?sample.fields:{},elapsed=progress;
    const w=Array.isArray(waste.leftInk)?waste.leftInk[0]:waste.leftInk;
    const wasteFilled=num(w)!==null && w>=0 && w<=10000 ? 100-w/100 : null;
    const wasteLevel=num(w)!==null && w>=0 && w<=10000?(w/100).toFixed(1)+'%':'—';
    const wasteColor=wasteFilled===null?'#94a3b8':wasteFilled>=80?'#fb7185':wasteFilled>=60?'#fbbf24':'#34d399';
    return `<section><h2>Latest decoded readings</h2><small>Received snapshots; may be stale when disconnected. These are observations, not control commands.</small>
      <div class="cards"><div class="card">Progress<strong>${num(progress.progress)!==null && progress.progress>=0 && progress.progress<=10000?esc(progress.progress/100)+'%':'—'}</strong></div><div class="card">Remaining time<strong>${num(progress.time)!==null?esc(this.duration(progress.time)):'—'}</strong></div><div class="card">Elapsed time<strong>${num(elapsed.totalTime)!==null?esc(this.duration(elapsed.totalTime)):'—'}</strong></div><div class="card">Waste tank filled<strong>${wasteFilled!==null?esc(wasteFilled.toFixed(1))+'%':'—'}</strong><div style="height:8px;background:#334155;border-radius:4px;margin:8px 0;overflow:hidden"><div data-waste-fill style="height:100%;width:${wasteFilled===null?0:wasteFilled}%;background:${wasteColor}"></div></div><small>Remaining capacity ${esc(wasteLevel)}</small><br><small>Expiry ${esc(expiry(waste.distanceExpiration))}</small></div></div>
      <h3>Ink Supply</h3><div class="cards">${['Cyan','Magenta','Yellow','Black','White','Gloss'].map((name,i)=>`<div class="card">${name}<strong>${esc(level(ink.leftInk?.[i]))}</strong><small>Expiry ${esc(expiry(ink.distanceExpiration?.[i]))}</small></div>`).join('')}</div><small>Ink received: ${esc(this.time(d.live?.['1100']?.time))} · Progress received: ${esc(this.time(d.live?.['1001']?.time))}</small></section>`;
  }
  freshness(d) {
    const age=(Date.now()-Date.parse(d.last_received))/1000;
    const stale=!d.connected||!Number.isFinite(age)||age<0||age>120;
    return `<p role="status" style="color:${stale?'#b45309':'var(--secondary-text-color)'}">${Number.isFinite(age)&&age>=0?'Updated '+this.esc(this.duration(age))+' ago':'No valid telemetry timestamp'}${stale?' · '+(!d.connected?'Disconnected':'Telemetry stale / unavailable'):''}</p>`;
  }
  historySection(d) {
    const h=d.decoded?.history||{},esc=x=>this.esc(x),last=(h.prints||[]).slice().reverse().find(p=>p.completion_confirmed),maintenance={};
    (h.maintenance||[]).forEach(m=>{maintenance[m.operation]=m;});
    const usage=p=>`<small>${esc(p.usage?.status||'Usage unavailable')}${typeof p.usage?.total_estimated_ml==='number'?' · '+esc(p.usage.total_estimated_ml.toFixed(2))+' mL estimated total':''}${p.reported_quantities?'<br>Printer quantities (units unverified): '+esc(JSON.stringify(p.reported_quantities)):''}</small>`;
    const sample=d.decoded?.readings?.['1001'],remaining=sample?.fields?.time,age=Date.now()-Date.parse(sample?.time),eta=d.connected&&d.current?.state===2&&d.current?.step===4&&typeof remaining==='number'&&Number.isFinite(remaining)&&remaining>=0&&age>=0&&age<=120000;
    const points=h.ink_history||[],colors=['#06b6d4','#ec4899','#eab308','#64748b','#94a3b8','#8b5cf6'];
    const chart=points.length>1?`<svg viewBox="0 0 600 120" role="img" aria-label="Ink Supply history, zero to 100 percent" style="width:100%;max-height:180px;background:#0f172a">${colors.map((color,i)=>'<polyline fill="none" stroke="'+color+'" stroke-width="2" points="'+points.map((p,j)=>{const start=Date.parse(points[0].time),span=Date.parse(points[points.length-1].time)-start;return typeof p.levels_percent?.[i]==='number'&&Number.isFinite(p.levels_percent[i])?((span>0?(Date.parse(p.time)-start)/span:j/(points.length-1))*600).toFixed(1)+','+(120-Math.max(0,Math.min(100,p.levels_percent[i]))*1.2).toFixed(1):'';}).join(' ')+'"/>').join('')}${points.map((p,j)=>p.cartridge_change?'<line stroke="#fbbf24" x1="'+(j/(points.length-1)*600)+'" x2="'+(j/(points.length-1)*600)+'" y1="0" y2="120"/>':'').join('')}</svg><small>${esc(this.time(points[0].time))} — ${esc(this.time(points[points.length-1].time))} · 0–100%, C/M/Y/K/W/G; vertical markers indicate reported identity changes.</small>`:'Collecting inventory history…';
    return `<section><h2>Observed history</h2>${eta?'<p>Estimated finish: '+esc(this.time(new Date(Date.parse(sample.time)+remaining*1000).toISOString()))+'</p>':''}${last?'<p><strong>Last completed print</strong> · '+esc(this.time(last.end))+' · Last reported elapsed '+esc(this.duration(last.elapsed_seconds))+'<br>'+usage(last)+'</p>':''}<details><summary>Print and maintenance summaries</summary>${(h.prints||[]).slice().reverse().map(p=>'<p>'+esc(p.completion_confirmed?'Print completed':'Print ended; completion unconfirmed')+' · '+esc(this.time(p.end))+' · '+esc(this.duration(p.elapsed_seconds))+'<br>'+usage(p)+'</p>').join('')}${Object.values(maintenance).map(m=>'<p>'+esc(m.operation)+' · '+esc(this.time(m.end))+' · '+esc(this.duration(m.duration_seconds))+'<br>'+usage(m)+'</p>').join('')}<p>Durations require both transitions without a connection gap. Persistent post-maintenance states are excluded.</p></details><details><summary>Connection history</summary>${(h.connections||[]).slice().reverse().map(c=>'<p>'+esc(this.time(c.time))+' · '+(c.connected?'Connected':'Disconnected')+(typeof c.previous_duration_seconds==='number'?' · Previous '+(c.previous_connected?'connection':'outage')+': '+esc(this.duration(c.previous_duration_seconds)):'')+'</p>').join('')}</details><details><summary>Ink Supply history and cartridge changes</summary>${chart}<p>Inventory includes print and maintenance usage. Boundary estimates assume 100 mL cartridges and may overlap adjacent operations. Gaps, inventory increases and identity changes invalidate estimates. Job quantity units remain unverified.</p>${(h.cartridge_changes||[]).slice().reverse().map(c=>'<p>'+esc(c.color)+' identity changed · '+esc(this.time(c.time))+' · '+esc(c.level_percent??'Unavailable')+'% · Expiration '+(c.expiration_timestamp?esc(new Date(c.expiration_timestamp*1000).toISOString().slice(0,10)):'unavailable')+'</p>').join('')||'<p>No reported cartridge identity changes observed.</p>'}</details></section>`;
  }
  sessionSection(d) {
    const esc=x=>this.esc(x),active=(d.recordings||[]).find(s=>s.id===d.active_recording);
    return `<details><summary>Named recording sessions and bookmarks</summary><p>${active?'Active session: '+esc(active.name)+' · '+esc(active.note||''):'No named session active. Ordinary capture continues.'}</p>${active?'<button data-action="end-session">End named session</button>':'<button data-action="start-session">Start named session</button>'}<label><input id="bookmarks-only" type="checkbox" ${this.bookmarksOnly?'checked':''}> Only bookmarks</label><button data-action="load-history">Load all retained records</button><p>Names and observations persist across restarts. Bookmarks follow normal retention limits; they do not protect records from deletion. Session exports include retained session records only.</p>${(d.recordings||[]).slice().reverse().map(s=>'<p>'+esc(s.name)+' · '+esc(this.time(s.start))+(s.end?' — '+esc(this.time(s.end)):' (active)')+' · '+esc(s.note||'')+(s.end_note?' · Final observation: '+esc(s.end_note):'')+' <button data-session-export="'+esc(s.id)+'">Export session JSON</button></p>').join('')}</details>`;
  }
  comparisonSection() {
    const c=this.comparison,esc=x=>this.esc(x);
    return `<details ${c?'open':''}><summary>Compare captured fields (${(this.compareIds||[]).length}/2 selected)</summary><p>Select two records using their Compare buttons. Only differences in the captured, redacted fields are shown.</p>${c?'<p>'+esc(this.time(c.first_time))+' → '+esc(this.time(c.second_time))+'</p><div class="scroll"><table><thead><tr><th>Field</th><th>First</th><th>Second</th></tr></thead><tbody>'+c.changes.map(x=>'<tr><td>'+esc(x.field)+'</td><td>'+esc(x.before_present?JSON.stringify(x.before):'Not captured')+'</td><td>'+esc(x.after_present?JSON.stringify(x.after):'Not captured')+'</td></tr>').join('')+'</tbody></table></div>'+(!c.changes.length?'<p>No captured field differences.</p>':''):''}<button data-action="clear-compare">Clear comparison</button></details>`;
  }
  downloadJSON(data, suffix) {
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');
    a.href=url;a.download='eufymake-activity-'+suffix+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }

  renderRows() {
    const body=this.shadowRoot.querySelector('#timeline-rows'); if(!body || !this.data)return;
    const filter=this.filter.toLowerCase();
    const rows=this.data.events.slice().reverse().filter(e=>!this.bookmarksOnly||e.bookmark).filter(e=>[this.pair(e),e.kind,e.command,e.note,this.meaning(e)].join(' ').toLowerCase().includes(filter));
    this.page=Math.max(0,Math.min(this.page||0,Math.max(0,Math.ceil(rows.length/300)-1)));
    const info=this.shadowRoot.querySelector('[data-page-info]');if(info)info.textContent='Page '+(this.page+1)+' of '+Math.max(1,Math.ceil(rows.length/300))+' · '+rows.length+' matching records';
    body.innerHTML=rows.slice(this.page*300,(this.page+1)*300).map(e=>
      `<tr><td>${this.esc(this.time(e.time))}</td><td>${this.esc(e.kind)}${e.command !== undefined ? ' / '+this.esc(e.command) : ''}</td><td>${this.esc(this.pair(e))}</td><td>${this.esc(this.meaning(e))}</td><td>${e.duration_seconds === undefined ? '—' : this.esc(e.duration_seconds)+' s'}</td><td>${this.esc(e.note||'')}</td><td><button data-bookmark="${this.esc(e.id)}" aria-pressed="${!!e.bookmark}">${e.bookmark?'★ Bookmarked':'☆ Bookmark'}</button><button data-compare="${this.esc(e.id)}" aria-pressed="${(this.compareIds||[]).includes(e.id)}">Compare</button><button data-edit="${this.esc(e.id)}">Details / note</button>${e.kind === 'status' ? `<button data-copy-pair="${this.esc(this.pair(e))}">Copy codes</button><button data-pair="${this.esc(this.pair(e))}">Label</button>` : ''}</td></tr>`).join('');
  }
  render() {
    const d=this.data,esc=x=>this.esc(x);
    const event=d?.events.find(e=>e.id===this.selected);
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100vh;font-family:system-ui}
      header{display:flex;align-items:center;gap:12px;padding:12px;border-bottom:1px solid var(--divider-color)}h1{font-size:21px;margin:0}
      main{padding:18px;max-width:1300px;margin:auto}.cards,.tools{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
      section,.card{background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:12px;padding:14px}.card{flex:1;min-width:150px}.card strong{display:block;margin-top:8px}
      button,input,textarea,select{font:inherit;border:1px solid var(--divider-color);border-radius:8px;padding:9px;background:var(--card-background-color);color:var(--primary-text-color)}button{cursor:pointer}button:focus-visible{outline:2px solid var(--primary-color)}input,textarea{box-sizing:border-box;max-width:100%}textarea{width:100%;min-height:90px}
      label{display:inline-block;margin:6px 12px 6px 0}small{color:var(--secondary-text-color)}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:9px;text-align:left;border-bottom:1px solid var(--divider-color);vertical-align:top}td{white-space:pre-wrap;overflow-wrap:anywhere}.error{color:var(--error-color)}details{margin:14px 0}p{line-height:1.5}
    </style><header><ha-menu-button></ha-menu-button><h1>E1 Activity Lab</h1></header><main>
      <p>Private activity recorder. Watch decoded telemetry, inspect unfamiliar command types, and label observations. Labels never change printer behavior.</p>
      ${this.error?`<p class="error" role="alert">${esc(this.error)}</p>`:''}
      ${!d?'<p>Connecting…</p>':`<div class="cards">
        <div class="card">Cloud connection<strong>${d.connected?'Connected':'Disconnected'}</strong></div>
        <div class="card">Current state / step<strong>${d.current?esc(d.current.state+'/'+d.current.step):'Not yet received'}</strong></div>
        <div class="card">Recording<strong>${d.recording?'Active':'Paused'}</strong></div>
        <div class="card">Last live message<strong>${esc(this.time(d.last_received))}</strong></div></div>
        ${this.freshness(d)}${this.decodedSection(d)}${this.liveSection(d)}${this.historySection(d)}${this.sessionSection(d)}${this.comparisonSection()}<div class="tools"><button data-action="marker">Mark observation now</button><button data-action="recording">${d.recording?'Pause':'Resume'} recording</button><button data-action="refresh">Refresh</button><button data-action="csv">Download CSV</button><button data-action="json">Download JSON backup</button></div>
        <p><small>${d.retained} of ${d.limit} records retained · ${d.dropped} oldest records removed · ${d.messages_this_session} decoded messages this session. Status transitions are immediate. Changed telemetry and unfamiliar commands are sampled at most once per command every 5 seconds. State residence ends at the next recorded transition or connection change. It is not continuous cleaning time; 13/0 and 13/1 are persistent post-maintenance states.</small></p>
        <section><h2>Timeline</h2><label>Filter <input id="filter" value="${esc(this.filter)}" placeholder="Pair, activity or note"></label><small>${this.allHistory?'All retained records loaded':'Latest 300 records shown'}; exports include all retained records. Times use America/Los_Angeles (including daylight saving).</small>
        <p><button data-action="previous-page">Previous page</button> <span data-page-info></span> <button data-action="next-page">Next page</button></p><div class="scroll"><table><thead><tr><th>Time</th><th>Event / command</th><th>State/step</th><th>Meaning</th><th>Observed state residence</th><th>Your observation</th><th></th></tr></thead><tbody id="timeline-rows"></tbody></table></div></section>
        ${event?`<section style="margin-top:14px"><h2>Observation at ${esc(this.time(event.time))}</h2>${event.fields ? `<details open><summary>Decoded fields (strings and sensitive fields omitted)</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify(event.fields,null,2))}</pre></details>` : ''}<form id="note"><textarea name="note" maxlength="1000" aria-label="Observation">${esc(event.note||'')}</textarea><button>Save observation</button><button type="button" data-action="close">Close</button></form></section>`:''}
        <details ${this.labelPair ? 'open' : ''}><summary>Label a state/step pair</summary><form id="label"><label>State <input name="state" type="number" value="${esc(this.labelPair?.split('/')[0] || '')}" required></label><label>Step <input name="step" type="number" value="${esc(this.labelPair?.split('/')[1] || '')}" required></label><label>Meaning <input name="label" maxlength="120" value="${esc(d.labels[this.labelPair]?.label || '')}" placeholder="e.g. Waiting for Start"></label><label>Confidence <select name="confidence"><option>suspected</option><option>confirmed</option></select></label><button>Save label</button><p><small>Use your own observations. An empty meaning removes the label. Existing history displays your latest label.</small></p></form>
        <div class="scroll"><table><thead><tr><th>Pair</th><th>Retained state reports</th><th>Label</th></tr></thead><tbody>${Object.entries(d.pairs).map(([pair,count])=>`<tr><td>${esc(pair)}</td><td>${count}</td><td>${esc(d.labels[pair]?.label||'Unlabeled')} ${esc(d.labels[pair]?.confidence||'')}</td></tr>`).join('')}</tbody></table></div></details>
        <details><summary>Capture settings and connection details</summary><form id="settings"><label><input name="telemetry" type="checkbox" ${d.capture_telemetry?'checked':''}> Record changed telemetry</label><label><input name="unknown" type="checkbox" ${d.capture_unknown?'checked':''}> Record unfamiliar commands</label><label>History limit <input name="retention" type="number" min="1000" max="50000" value="${d.limit}" required></label><button>Save capture settings</button></form><p>Command counts this session: ${esc(JSON.stringify(d.commands_this_session))}</p><p>Total decoded command counts: ${esc(JSON.stringify(d.total_commands))}</p><p>Transport diagnostics this session: ${esc(JSON.stringify(d.diagnostics))}</p><p>History and labels persist across restarts. Current connection, message counts and last-message time reset at startup. A separate MQTT identity is used. No print commands are sent; a telemetry query is sent every 30 seconds. Complete single frames are decoded; fragmented frames are currently ignored. Very brief statuses can be missed if the cloud does not deliver them.</p><p>Decoded fields retain numeric values, booleans, and structure. Text values and recognizable sensitive field names are omitted. Unknown numeric fields can still need review before sharing an export. Full wire payloads are not stored. Do not type credentials into observations.</p><button data-action="clear">Clear retained history</button></details>`}
    </main>`;
    const menu=this.shadowRoot.querySelector('ha-menu-button');menu.hass=this._hass;menu.narrow=this._narrow;
    this.renderRows();
  }
  async click(e) {
    const button=e.target.closest('button');if(!button)return;
    if(button.dataset.copyPair){
      const text='EufyMake E1 state/step='+button.dataset.copyPair;
      try {
        if(navigator.clipboard)await navigator.clipboard.writeText(text);
        else {const area=document.createElement('textarea');area.value=text;this.shadowRoot.appendChild(area);area.select();const copied=document.execCommand('copy');area.remove();if(!copied)throw new Error('Copy unavailable');}
        button.textContent='Copied';
      }catch(_){button.textContent='Copy unavailable; select displayed codes';}return;
    }
    if(button.dataset.bookmark){
      const event=this.data.events.find(x=>x.id===button.dataset.bookmark);
      try {await this.request('bookmark',{id:event.id,enabled:!event.bookmark});event.bookmark=!event.bookmark;await this.refresh();}catch(error){this.error=error.message;this.render();}return;
    }
    if(button.dataset.compare){
      const id=button.dataset.compare;this.compareIds=this.compareIds||[];
      this.compareIds=this.compareIds.includes(id)?this.compareIds.filter(x=>x!==id):this.compareIds.slice(-1).concat(id);
      this.comparison=null;
      try {if(this.compareIds.length===2)this.comparison=await this.request('compare',{first:this.compareIds[0],second:this.compareIds[1]});this.render();}catch(error){this.error=error.message;this.render();}return;
    }
    if(button.dataset.sessionExport){try {const full=await this.request('export',{recording_session:button.dataset.sessionExport});this.downloadJSON(full,'session-'+button.dataset.sessionExport);}catch(error){this.error=error.message;this.render();}return;}
    if(button.dataset.edit){this.selected=button.dataset.edit;this.render();return;}
    if(button.dataset.pair){this.labelPair=button.dataset.pair;this.render();this.shadowRoot.querySelector('#label').scrollIntoView?.();return;}
    const action=button.dataset.action;if(!action)return;
    try {
      if(action==='load-history'){const full=await this.request('export');this.fullEvents=full.events;this.allHistory=true;this.page=0;await this.refresh();return;}
      if(action==='previous-page'||action==='next-page'){this.page=Math.max(0,(this.page||0)+(action==='next-page'?1:-1));this.renderRows();return;}
      if(action==='clear-compare'){this.compareIds=[];this.comparison=null;this.render();return;}
      if(action==='start-session'){
        const name=prompt('Name this recording session (up to 120 characters):');if(!name?.trim())return;
        const note=prompt('Session observation (optional, no credentials):');if(note===null)return;
        this.data=await this.request('session',{name,note});
      }
      if(action==='end-session'){
        const note=prompt('Final session observation (optional):');if(note===null)return;
        this.data=await this.request('session',{end:true,note});
      }
      if(action==='close'){this.selected=null;this.render();return;}
      if(action==='refresh'){await this.refresh();return;}
      if(action==='marker'){const note=prompt('What is Studio or the printer doing right now?');if(!note?.trim())return;this.data=await this.request('marker',{note});}
      if(action==='recording')this.data=await this.request('recording',{enabled:!this.data.recording});
      if(action==='clear'){
        if(prompt('Export first if needed. Type CLEAR to delete retained history; labels are kept.')!=='CLEAR')return;
        this.data=await this.request('clear',{confirm:'CLEAR'});this.selected=null;this.fullEvents=null;this.allHistory=false;this.page=0;
      }
      if(action==='csv'||action==='json'){
        const full=await this.request('export');
        const cell=x=>{let s=String(x??'');if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
        const csv=[['time_utc','session','kind','state','step','label','confidence','duration_seconds','command','decoded_fields_json','note','detail'],...full.events.map(r=>{const l=full.labels[`${r.state}/${r.step}`]||{};return [r.time,r.session,r.kind,r.state,r.step,l.label,l.confidence,r.duration_seconds,r.command,r.fields?JSON.stringify(r.fields):'',r.note,r.detail||this.meaning(r)];})].map(row=>row.map(cell).join(',')).join('\r\n');
        const blob=new Blob([action==='json'?JSON.stringify(full,null,2):'\ufeff'+csv],{type:action==='json'?'application/json':'text/csv;charset=utf-8'});
        const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='eufymake-activity-'+new Date().toISOString().slice(0,10)+'.'+action;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;
      }
      this.error='';this.render();
    }catch(error){this.error=error.message||'Request failed';this.render();}
  }
  async submit(e) {
    e.preventDefault();const form=e.target;if(!['note','label','settings'].includes(form.id))return;
    const fields=new FormData(form);
    const action=form.id,data=action==='settings'?{telemetry:fields.has('telemetry'),unknown:fields.has('unknown'),retention:Number(fields.get('retention'))}:action==='note'?{id:this.selected,note:fields.get('note')}:
      {state:Number(fields.get('state')),step:Number(fields.get('step')),label:fields.get('label'),confidence:fields.get('confidence')};
    try {this.data=await this.request(action,data);if(action==='note'&&this.fullEvents){const event=this.fullEvents.find(e=>e.id===data.id);if(event)event.note=data.note;}this.selected=null;this.labelPair=null;this.error='';this.render();}
    catch(error){this.error=error.message||'Could not save';this.render();}
  }
}
if(!customElements.get('eufymake-activity-lab'))customElements.define('eufymake-activity-lab',EufyMakeActivityLab);
