// Fixture-only execution of the actual matching-page script, with no network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('matches/templates/matches/find_matches.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
async function check(featured) {
  let click, submit, active, fetches = 0;
  function button() {
    return {dataset: {id:'7',name:'Partner',teach:'English',learn:'Korean'},
      closest() { return featured ? null : {querySelector() {return {};}}; },
      replaceWith(node) {this.replacement = node;}};
  }
  const opener=button(), duplicate=button(), unrelated=button();
  unrelated.dataset.id="8";
  const els = Object.fromEntries(['requestDialog','matchesContainer','resultCount','reqName','reqSwap','reqError','requestMessage','charCount','requestForm','reqSend'].map(id=>[id,{textContent:'',value:'',hidden:true,addEventListener(type,fn){if(id==='requestForm')submit=fn;},focus(){active=this;}}]));
  els.requestDialog.showModal=()=>{}; els.requestDialog.close=()=>{active=opener;};
  const doc={getElementById:id=>els[id],addEventListener(type,fn){click=fn;},
    querySelectorAll:()=>[opener,duplicate,unrelated],createElement:()=>({className:'',setAttribute(){},focus(){active=this;}})};
  vm.runInNewContext(script,{document:doc,FormData:class{append(){}},fetch:()=>{fetches++;return Promise.resolve({json:()=>Promise.resolve({success:true,message:'Sent'})});}});
  click({target:{closest:sel=>sel==='[data-open-request]'?opener:null}});
  submit({preventDefault(){}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(fetches,1);
  assert.equal(els.reqError.hidden,true,'success must not become a connection error');
  assert.equal(els.resultCount.textContent,'Sent');
  assert.ok(opener.replacement,'replace the clicked request entry');
  assert.ok(duplicate.replacement,'replace duplicate entry for same suggestion');
  assert.equal(active,opener.replacement,'focus the clicked confirmation');
  assert.equal(unrelated.replacement,undefined,'leave other suggestions alone');
}
(async()=>{await check(false);await check(true);console.log('request success: card and featured PASS');})().catch(e=>{console.error(e);process.exit(1);});
