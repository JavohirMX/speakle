// Execute the actual socket-close callback; no account or network access.
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('chats/templates/chats/video_room.html','utf8');
const match=source.match(/this\.ws\.onclose = \(event\) => \{([\s\S]*?)\n        \};/);assert.ok(match);
let resets=0,reconnects=0,timer;
const client={isWebSocketReady:true,isCallActive:true,pendingPeerReadySignals:[{}],updateStatus(){},resetCall(){resets++;this.isCallActive=false;},connectWebSocket(){reconnects++;}};
new Function('setTimeout',match[1]).call(client,(fn,delay)=>{assert.equal(delay,3000);timer=fn;});
assert.equal(resets,1);assert.equal(client.isCallActive,false);assert.equal(client.isWebSocketReady,false);assert.deepEqual(client.pendingPeerReadySignals,[]);timer();assert.equal(reconnects,1);
console.log('call socket recovery PASS');
