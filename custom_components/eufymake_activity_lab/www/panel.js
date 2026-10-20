class EufyMakeActivityLab extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:'open'}); this.filter=''; this.selected=null;
    this.shadowRoot.addEventListener('click', e => this.click(e));
    this.shadowRoot.addEventListener('submit', e => this.submit(e));
    this.shadowRoot.addEventListener('input', e => {
      if (e.target.id === 'filter') { this.filter=e.target.value; this.renderRows(); }
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
    try { this.data=await this.request(); this.error=''; if(!this.shadowRoot.activeElement?.matches('input,textarea,select'))this.render(); }
    catch(e) { this.error=e.message || 'Connection unavailable'; this.render(); }
    finally {this.busy=false;}
  }
  esc(x) { return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  time(x) { return x ? new Date(x).toLocaleString(this._hass?.locale?.language||'en-US',{timeZone:'America/Los_Angeles',timeZoneName:'short'}) : 'Not yet received'; }
  pair(e) { return e.kind==='status' ? `${e.state}/${e.step}` : ''; }
  meaning(e) { const p=this.pair(e),l=this.data.labels[p]; return l ? `${l.label} (${l.confidence})` : e.detail || (p ? this.builtinMeaning(e) : ''); }
  builtinMeaning(e) {
    const labels={'0/0':'Idle','2/1':'Transferring print file','2/2':'Waiting for Start','2/3':'Paused','2/4':'Printing','2/6':'Priming print head','5/3':'Injecting ink','5/7':'Automatic flash clean','5/9':'Automatic moisturizing','5/10':'Automatic deep cleaning','6/1':'Updating firmware','8/0':'Taking snapshot','9/0':'Calibration / self-check','13/0':'Post-moisturizing maintenance (inferred)','13/1':'Post-deep-clean maintenance'};
    return labels[this.pair(e)] || 'Unknown (' + this.pair(e) + ')';
  }
  duration(value) {
    if(typeof value!=='number'||!Number.isFinite(value)||value<0)return '—';
    const n=Math.floor(value),h=Math.floor(n/3600),m=Math.floor(n%3600/60);
    return (h?h+'h ':'')+(m||h?m+'m ':'')+(n%60)+'s';
  }
  decodedSection(d) {
    const decoded=d.decoded||{},hw=decoded.hardware||{},read=decoded.readings||{}, activity=read.activity;
    const fresh=x=>d.connected && x?.time && Date.now()-new Date(x.time).getTime()>=0 && Date.now()-new Date(x.time).getTime()<=120000;
    const device=x=>x?`${this.esc(x.label)} · code ${this.esc(x.code)} · command ${this.esc(x.source_command)}${x.reply!==undefined?' · raw reply '+this.esc(x.reply):''} · ${this.esc(this.time(x.time))}`:'Not reported';
    return `<section><h2>Printer and accessory observations</h2><p>Bed: ${device(hw.bed)}</p><p>Accessory: ${device(hw.accessory)}</p><p>${this.esc(hw.consistency||'Waiting for reports')}. Last reports may be stale; raw sources remain independent.</p><p>Activity: ${this.esc(decoded.status||'Waiting for status')} ${activity?'· '+this.esc(activity.operation)+' progress: '+(fresh(activity)&&activity.progress!==null?this.esc(activity.progress)+'%':'Unavailable / stale'):''}</p></section>`;
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
    const wasteLevel=num(w)!==null && w>=0 && w<=10000?(w/100).toFixed(1)+'%':'—';
    return `<section><h2>Latest decoded readings</h2><small>Received snapshots; may be stale when disconnected. These are observations, not control commands.</small>
      <div class="cards"><div class="card">Progress<strong>${num(progress.progress)!==null && progress.progress>=0 && progress.progress<=10000?esc(progress.progress/100)+'%':'—'}</strong></div><div class="card">Remaining time<strong>${num(progress.time)!==null?esc(this.duration(progress.time)):'—'}</strong></div><div class="card">Elapsed time<strong>${num(elapsed.totalTime)!==null?esc(this.duration(elapsed.totalTime)):'—'}</strong></div><div class="card">Waste capacity<strong>${esc(wasteLevel)}</strong><small>Expiry ${esc(expiry(waste.distanceExpiration))}</small></div></div>
      <div class="cards">${['Cyan','Magenta','Yellow','Black','White','Gloss'].map((name,i)=>`<div class="card">${name}<strong>${esc(level(ink.leftInk?.[i]))}</strong><small>Expiry ${esc(expiry(ink.distanceExpiration?.[i]))}</small></div>`).join('')}</div><small>Ink received: ${esc(this.time(d.live?.['1100']?.time))} · Progress received: ${esc(this.time(d.live?.['1001']?.time))}</small></section>`;
  }
  renderRows() {
    const body=this.shadowRoot.querySelector('tbody'); if(!body || !this.data)return;
    const filter=this.filter.toLowerCase();
    body.innerHTML=this.data.events.slice().reverse().filter(e=>[this.pair(e),e.kind,e.command,e.note,this.meaning(e)].join(' ').toLowerCase().includes(filter)).map(e=>
      `<tr><td>${this.esc(this.time(e.time))}</td><td>${this.esc(e.kind)}${e.command !== undefined ? ' / '+this.esc(e.command) : ''}</td><td>${this.esc(this.pair(e))}</td><td>${this.esc(this.meaning(e))}</td><td>${e.duration_seconds === undefined ? '—' : this.esc(e.duration_seconds)+' s'}</td><td>${this.esc(e.note||'')}</td><td><button data-edit="${this.esc(e.id)}">Details / note</button>${e.kind === 'status' ? `<button data-pair="${this.esc(this.pair(e))}">Label</button>` : ''}</td></tr>`).join('');
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
        ${this.decodedSection(d)}${this.liveSection(d)}<div class="tools"><button data-action="marker">Mark observation now</button><button data-action="recording">${d.recording?'Pause':'Resume'} recording</button><button data-action="refresh">Refresh</button><button data-action="csv">Download CSV</button><button data-action="json">Download JSON backup</button></div>
        <p><small>${d.retained} of ${d.limit} records retained · ${d.dropped} oldest records removed · ${d.messages_this_session} decoded messages this session. Status transitions are immediate. Changed telemetry and unfamiliar commands are sampled at most once per command every 5 seconds. State residence ends at the next recorded transition or connection change. It is not continuous cleaning time; 13/0 and 13/1 are persistent post-maintenance states.</small></p>
        <section><h2>Timeline</h2><label>Filter <input id="filter" value="${esc(this.filter)}" placeholder="Pair, activity or note"></label><small>Latest 300 records shown; exports include all retained records. Times use America/Los_Angeles (including daylight saving).</small>
        <div class="scroll"><table><thead><tr><th>Time</th><th>Event / command</th><th>State/step</th><th>Meaning</th><th>Observed state residence</th><th>Your observation</th><th></th></tr></thead><tbody></tbody></table></div></section>
        ${event?`<section style="margin-top:14px"><h2>Observation at ${esc(this.time(event.time))}</h2>${event.fields ? `<details open><summary>Decoded fields (strings and sensitive fields omitted)</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify(event.fields,null,2))}</pre></details>` : ''}<form id="note"><textarea name="note" maxlength="1000" aria-label="Observation">${esc(event.note||'')}</textarea><button>Save observation</button><button type="button" data-action="close">Close</button></form></section>`:''}
        <details ${this.labelPair ? 'open' : ''}><summary>Label a state/step pair</summary><form id="label"><label>State <input name="state" type="number" value="${esc(this.labelPair?.split('/')[0] || '')}" required></label><label>Step <input name="step" type="number" value="${esc(this.labelPair?.split('/')[1] || '')}" required></label><label>Meaning <input name="label" maxlength="120" value="${esc(d.labels[this.labelPair]?.label || '')}" placeholder="e.g. Waiting for Start"></label><label>Confidence <select name="confidence"><option>suspected</option><option>confirmed</option></select></label><button>Save label</button><p><small>Use your own observations. An empty meaning removes the label. Existing history displays your latest label.</small></p></form>
        <div class="scroll"><table><thead><tr><th>Pair</th><th>Retained transitions</th><th>Label</th></tr></thead><tbody>${Object.entries(d.pairs).map(([pair,count])=>`<tr><td>${esc(pair)}</td><td>${count}</td><td>${esc(d.labels[pair]?.label||'Unlabeled')} ${esc(d.labels[pair]?.confidence||'')}</td></tr>`).join('')}</tbody></table></div></details>
        <details><summary>Capture settings and connection details</summary><form id="settings"><label><input name="telemetry" type="checkbox" ${d.capture_telemetry?'checked':''}> Record changed telemetry</label><label><input name="unknown" type="checkbox" ${d.capture_unknown?'checked':''}> Record unfamiliar commands</label><label>History limit <input name="retention" type="number" min="1000" max="50000" value="${d.limit}" required></label><button>Save capture settings</button></form><p>Command counts this session: ${esc(JSON.stringify(d.commands_this_session))}</p><p>Total decoded command counts: ${esc(JSON.stringify(d.total_commands))}</p><p>Transport diagnostics this session: ${esc(JSON.stringify(d.diagnostics))}</p><p>History and labels persist across restarts. Current connection, message counts and last-message time reset at startup. A separate MQTT identity is used. No print commands are sent; a telemetry query is sent every 30 seconds. Complete single frames are decoded; fragmented frames are currently ignored. Very brief statuses can be missed if the cloud does not deliver them.</p><p>Decoded fields retain numeric values, booleans, and structure. Text values and recognizable sensitive field names are omitted. Unknown numeric fields can still need review before sharing an export. Full wire payloads are not stored. Do not type credentials into observations.</p><button data-action="clear">Clear retained history</button></details>`}
    </main>`;
    const menu=this.shadowRoot.querySelector('ha-menu-button');menu.hass=this._hass;menu.narrow=this._narrow;
    this.renderRows();
  }
  async click(e) {
    const button=e.target.closest('button');if(!button)return;
    if(button.dataset.edit){this.selected=button.dataset.edit;this.render();return;}
    if(button.dataset.pair){this.labelPair=button.dataset.pair;this.render();this.shadowRoot.querySelector('#label').scrollIntoView?.();return;}
    const action=button.dataset.action;if(!action)return;
    try {
      if(action==='close'){this.selected=null;this.render();return;}
      if(action==='refresh'){await this.refresh();return;}
      if(action==='marker'){const note=prompt('What is Studio or the printer doing right now?');if(!note?.trim())return;this.data=await this.request('marker',{note});}
      if(action==='recording')this.data=await this.request('recording',{enabled:!this.data.recording});
      if(action==='clear'){
        if(prompt('Export first if needed. Type CLEAR to delete retained history; labels are kept.')!=='CLEAR')return;
        this.data=await this.request('clear',{confirm:'CLEAR'});this.selected=null;
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
    try {this.data=await this.request(action,data);this.selected=null;this.labelPair=null;this.error='';this.render();}
    catch(error){this.error=error.message||'Could not save';this.render();}
  }
}
if(!customElements.get('eufymake-activity-lab'))customElements.define('eufymake-activity-lab',EufyMakeActivityLab);
