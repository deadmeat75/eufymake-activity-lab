const {JSDOM}=require('jsdom');
const fs=require('fs'),assert=require('assert');
(async()=>{
 const dom=new JSDOM('<body></body>',{runScripts:'outside-only',url:'https://example.invalid'}),w=dom.window;
 w.eval(fs.readFileSync(require('path').join(__dirname,'../custom_components/eufymake_activity_lab/www/panel.js'),'utf8'));
 const calls=[],data={connected:true,recording:true,current:{state:2,step:2},last_received:'2026-10-10T06:30:44Z',messages_this_session:10,commands_this_session:{1000:5,9000:1},total_commands:{1000:20},diagnostics:{fragmented_frame:2},retained:2,limit:10000,dropped:0,capture_telemetry:true,capture_unknown:true,labels:{},pairs:{'2/2':1},live:{1100:{time:'2026-10-10T06:30:44Z',fields:{ink:{leftInk:[6550,7000,8000,9000,10000,0],distanceExpiration:[10,20,30,40,50,null]},wasteInk:{leftInk:[2500],distanceExpiration:100}}},1001:{time:'2026-10-10T06:30:44Z',fields:{progress:5000,time:30}}},events:[{id:'s',time:'2026-10-10T06:30:44Z',kind:'status',state:2,step:2,note:''},{id:'u',time:'2026-10-10T06:30:44Z',kind:'unknown',command:9000,fields:{temperature:32,text:'<text omitted>'},note:''}]};
 w.prompt=()=> 'Pressed Start';
 const p=w.document.createElement('eufymake-activity-lab');w.document.body.append(p);
 p.hass={config:{time_zone:'America/Los_Angeles'},callWS:async req=>{calls.push(req);return structuredClone(data);}};p.panel={config:{entry_id:'test'}};
 await new Promise(r=>setTimeout(r,20));
 assert(p.shadowRoot.textContent.includes('65.5% / 65.5 mL'));assert(p.shadowRoot.textContent.includes('25.0%'));
 p.shadowRoot.querySelector('[data-pair]').click();assert.strictEqual(p.shadowRoot.querySelector('[name="state"]').value,'2');assert.strictEqual(p.shadowRoot.querySelector('[name="step"]').value,'2');
 p.shadowRoot.querySelector('[data-action="marker"]').click();await new Promise(r=>setTimeout(r,10));assert(calls.some(c=>c.action==='marker'&&c.data.note==='Pressed Start'));
 p.shadowRoot.querySelector('[data-edit="u"]').click();assert(p.shadowRoot.querySelector('pre').textContent.includes('temperature'));
 const form=p.shadowRoot.querySelector('#settings');form.querySelector('[name="unknown"]').checked=false;form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,10));assert(calls.some(c=>c.action==='settings'&&c.data.unknown===false&&c.data.retention===10000));
 const filter=p.shadowRoot.querySelector('#filter');filter.value='9000';filter.dispatchEvent(new w.Event('input',{bubbles:true}));assert.strictEqual(p.shadowRoot.querySelectorAll('section tbody tr').length,1);
 dom.window.close();console.log('Expanded UI passed: live ink/waste, observation marker, prefilled labels, decoded details, settings and command filter.');
})().catch(e=>{console.error(e);process.exit(1)});
