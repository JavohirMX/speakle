// Execute the actual incoming-call keyboard handler. No account or network access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('main/templates/base.html','utf8');
const match = source.match(/\/\/ Keyboard navigation for modal\s+document.addEventListener\('keydown', function\(e\) \{([\s\S]*?)\n        \}\);/);
assert.ok(match);
let accepts=0,declines=0;
const modal={classList:{contains:()=>false}};
const document={getElementById:()=>modal};
const handler=new Function('document','globalAcceptCall','globalDeclineCall', 'return function(e){'+match[1]+'}')(document,()=>accepts++,()=>declines++);
handler({key:'Enter',target:{tagName:'BUTTON'},preventDefault(){}});
assert.equal(accepts,0,'Enter must activate the focused button, not force accept');
handler({key:'Enter',isComposing:true,target:{tagName:'INPUT'},preventDefault(){}});
assert.equal(accepts,0,'composition Enter must not accept a call');
handler({key:'Escape',preventDefault(){}});
assert.equal(declines,1,'Escape still declines');
console.log('incoming call keyboard PASS');
