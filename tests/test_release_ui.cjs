const {JSDOM}=require('jsdom'),fs=require('fs'),assert=require('assert'),path=require('path');
(async()=>{
 const dom=new JSDOM('<body></body>',{runScripts:'outside-only',url:'https://example.invalid'}),w=dom.window;
 w.eval(fs.readFileSync(path.join(__dirname,'../custom_components/eufymake_activity_lab/www/panel.js'),'utf8'));
 w.Date.now=()=>Date.parse('2026-10-27T19:24:10Z');
 const base={connected:true,recording:true,current:{state:0,step:0},last_received:'2026-10-27T19:24:05Z',retained:2,limit:10000,dropped:0,labels:{},pairs:{},events:[{id:'a',time:'2026-10-27T19:00:00Z',kind:'unknown',command:1118,fields:{plateType:0},note:''},{id:'b',time:'2026-10-27T19:00:10Z',kind:'unknown',command:1118,fields:{plateType:2},note:''}],recordings:[],decoded:{hardware:{bed:{label:'Mini Flatbed',code:2,source_command:1118,time:'2026-10-27T19:24:05Z'},bed_present:true},history:{prints:[{end:'2026-10-27T19:24:05Z',completion_confirmed:true,elapsed_seconds:1194,usage:{status:'Unavailable'}}],maintenance:[],connections:[],ink_history:[],cartridge_changes:[]}}};
 const calls=[],prompts=['Latch <test>','No private info','Finished'];w.prompt=()=>prompts.shift();w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){};
 const p=w.document.createElement('eufymake-activity-lab');w.document.body.append(p);
 p.hass={callWS:async req=>{
  calls.push(req);
  if(req.action==='compare')return {first:'a',second:'b',first_time:base.events[0].time,second_time:base.events[1].time,changes:[{field:'$.plateType',before:0,after:2,before_present:true,after_present:true}]};
  if(req.action==='bookmark')base.events.find(x=>x.id===req.data.id).bookmark=req.data.enabled;
  if(req.action==='session'){
   if(req.data.end){base.recordings[0].end='2026-10-27T19:25:00Z';base.active_recording=null;}
   else {base.active_recording='s1';base.recordings=[{id:'s1',name:req.data.name,note:req.data.note,start:'2026-10-27T19:24:00Z'}];}
  }
  return structuredClone(base);
 }};p.panel={config:{entry_id:'test'}};
 await new Promise(r=>setTimeout(r,20));
 try {
  assert(p.shadowRoot.textContent.includes('Updated 5s ago'));assert(p.shadowRoot.textContent.includes('19m 54s'));
  assert(p.shadowRoot.textContent.includes('13.19 × 3.54 in'));assert(p.shadowRoot.textContent.includes('Ink Supply'));
  p.shadowRoot.querySelector('[data-bookmark="a"]').click();await new Promise(r=>setTimeout(r,10));
  assert(calls.some(x=>x.action==='bookmark'&&x.data.id==='a'&&x.data.enabled));
  const only=p.shadowRoot.querySelector('#bookmarks-only');only.checked=true;only.dispatchEvent(new w.Event('input',{bubbles:true}));
  assert.strictEqual(p.shadowRoot.querySelectorAll('section tbody tr').length,1);p.bookmarksOnly=false;p.render();
  p.shadowRoot.querySelector('[data-compare="a"]').click();await new Promise(r=>setTimeout(r,5));
  p.shadowRoot.querySelector('[data-compare="b"]').click();await new Promise(r=>setTimeout(r,5));
  assert(p.shadowRoot.textContent.includes('$.plateType'));
  assert(calls.some(x=>x.action==='compare'&&x.data.first==='a'&&x.data.second==='b'));
  p.shadowRoot.querySelector('[data-action="start-session"]').click();await new Promise(r=>setTimeout(r,10));
  assert(p.shadowRoot.textContent.includes('Latch <test>'));assert(!p.shadowRoot.innerHTML.includes('Latch <test>'));
  p.shadowRoot.querySelector('[data-session-export="s1"]').click();await new Promise(r=>setTimeout(r,10));
  assert(calls.some(x=>x.action==='export'&&x.data.recording_session==='s1'));
  p.shadowRoot.querySelector('[data-action="end-session"]').click();await new Promise(r=>setTimeout(r,10));
  assert(calls.some(x=>x.action==='session'&&x.data.end));
  base.decoded.history={};base.last_received='2026-10-27T19:00:00Z';p.data=base;p.render();assert(p.shadowRoot.textContent.includes('Telemetry stale'));
  p.data.events=Array.from({length:601},(_,i)=>({id:'row'+i,time:'2026-10-27T19:00:00Z',kind:'unknown',command:9000,note:''}));p.page=0;p.render();
  assert.strictEqual(p.shadowRoot.querySelectorAll('#timeline-rows tr').length,300);
  await p.click({target:p.shadowRoot.querySelector('[data-action="next-page"]')});
  assert(p.shadowRoot.querySelector('[data-page-info]').textContent.includes('Page 2 of 3'));
  p.data.events=[{id:'unknown',time:'2026-10-27T19:00:00Z',kind:'status',state:8,step:2}];p.render();
  assert(p.shadowRoot.textContent.includes('Meaning not yet confirmed'));
  let copied='';Object.defineProperty(w.navigator,'clipboard',{configurable:true,value:{writeText:async value=>{copied=value;}}});
  await p.click({target:p.shadowRoot.querySelector('[data-copy-pair]')});assert.strictEqual(copied,'EufyMake E1 state/step=8/2');
 } finally {dom.window.close();}
 console.log('Release UI passed: history, freshness, dimensions, bookmark filter, comparison, session creation/end/export and escaped names.');
})().catch(e=>{console.error(e);process.exit(1)});
