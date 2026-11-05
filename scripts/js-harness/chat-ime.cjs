// Execute the actual Enter listeners with composition and normal-key fixtures.
const assert = require('node:assert/strict');
const fs = require('node:fs');
for (const [file, field, method] of [
  ['text_chat.html', 'messageInput', 'sendMessage'],
  ['video_room.html', 'chatInput', 'sendChatMessage'],
]) {
  const source = fs.readFileSync('chats/templates/chats/'+file, 'utf8');
  const match = source.match(new RegExp('this\\.'+field+"\\.addEventListener\\('key(?:down|press)', \\(e\\) => \\{([\\s\\S]*?)\\n        \\}\\);"));
  assert.ok(match, 'actual Enter listener must be found');
  const callback = new Function('e', match[1]);
  let sends=0, prevented=0;
  const chat = {[method]:()=>sends++};
  const key = props => ({key:'Enter',shiftKey:false,isComposing:false,keyCode:13,
    preventDefault(){prevented++;},...props});
  callback.call(chat,key({isComposing:true}));
  callback.call(chat,key({keyCode:229}));
  assert.equal(sends,0,file+': IME candidate confirmation must not send');
  assert.equal(prevented,0,file+': IME confirmation must keep native behavior');
  callback.call(chat,key({shiftKey:true}));
  assert.equal(sends,0,file+': Shift+Enter must not send');
  callback.call(chat,key({}));
  assert.equal(sends,1,file+': ordinary Enter sends once');
  assert.equal(prevented,1,file+': ordinary Enter prevents native newline');
}
console.log('chat IME Enter guards PASS');
