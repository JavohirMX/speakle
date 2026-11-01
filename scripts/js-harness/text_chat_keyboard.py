"""Text-chat keyboard-operability regression: drives the edit dialog with
real key and mouse input (CDP Input domain, trusted events) and pins the
behaviors from the held a11y patch (commits e0921d4/7b46087):

- Reply/Edit stay keyboard reachable (.message-actions hidden with opacity,
  not display:none, so the buttons can take focus; :focus-within reveals them)
- Enter on the Edit button opens the dialog and focus lands in the textarea
- Tab / Shift+Tab stay trapped inside the open dialog
- Escape closes the dialog and focus returns to the Edit button
- A real click on the edit icon (the SVG inside the button) opens the dialog

Runs against plain runserver: messages render server-side, so no websocket
is needed. Expects the fixture chat room to hold one message from the
fixture user (seeded by setup_fixtures.py).
"""
import json, time, urllib.request
from websocket import create_connection

import os as _os, json as _json
try:
    _fx = _json.load(open(_os.path.join(_os.path.dirname(__file__), 'fixtures.json')))
except Exception:
    _fx = {}
BASE = _fx.get('base_url', 'http://127.0.0.1:8000')
CDP = _fx.get('cdp_url', 'http://127.0.0.1:9223')
FXU = _fx.get('user', 'a11ydemo'); FXP = _fx.get('password', 'fixture-pass-123')
FXC = _fx.get('chat_room_id', '9edbfeae-f6ac-4fbf-9ce1-880b732cf9fe')

errors = []
ts = json.load(urllib.request.urlopen(CDP + '/json'))
t = [x for x in ts if x.get('type') == 'page'][0]
ws = create_connection(t['webSocketDebuggerUrl'], timeout=60); mid = [0]

def cmd(m, **p):
    mid[0] += 1
    ws.send(json.dumps({'id': mid[0], 'method': m, 'params': p}))
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == mid[0]:
            if 'error' in r: raise Exception(r['error'])
            return r.get('result', {})

def ev(e):
    return cmd('Runtime.evaluate', expression=e, returnByValue=True, awaitPromise=True).get('result', {}).get('value')

def key(k, code, vk, mods=0, text=None):
    # keyDown (not rawKeyDown) + text is what makes Chrome run the default
    # activation behavior, e.g. Enter clicking the focused button.
    down = dict(type='keyDown', key=k, code=code, windowsVirtualKeyCode=vk, modifiers=mods)
    if text: down['text'] = text
    cmd('Input.dispatchKeyEvent', **down)
    cmd('Input.dispatchKeyEvent', type='keyUp', key=k, code=code,
        windowsVirtualKeyCode=vk, modifiers=mods)

def click_at(x, y):
    cmd('Input.dispatchMouseEvent', type='mousePressed', x=x, y=y, button='left', clickCount=1)
    cmd('Input.dispatchMouseEvent', type='mouseReleased', x=x, y=y, button='left', clickCount=1)

def wait_for(expr, label, timeout=6):
    end = time.time() + timeout
    while time.time() < end:
        if ev(expr): return True
        time.sleep(0.3)
    errors.append('timeout waiting for ' + label)
    return False

MODAL_OPEN = "document.getElementById('editModal') && document.getElementById('editModal').style.display === 'flex'"
MODAL_CLOSED = "document.getElementById('editModal') && document.getElementById('editModal').style.display !== 'flex'"

cmd('Network.enable'); cmd('Network.clearBrowserCookies')
cmd('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)
cmd('Page.navigate', url=BASE + '/users/login/'); time.sleep(2)
ev("var u=document.getElementById('id_username'); u.value='" + FXU +
   "'; document.getElementById('id_password').value='" + FXP + "'; u.closest('form').submit(); 1")
time.sleep(3)
cmd('Page.navigate', url=BASE + '/chats/text/' + FXC + '/'); time.sleep(3)

seed = wait_for("!!document.querySelector('.message.own .edit-btn')", 'seeded own message with edit button')

# 1. Keyboard reachability: focusing the button must reveal the actions bar
#    (opacity 0 -> 1 via :focus-within; display:none would make it unfocusable).
ev("var b=document.querySelector('.message.own .edit-btn'); if(b) b.focus(); 1")
focused = ev("document.activeElement && document.activeElement.classList.contains('edit-btn')")
reveals = wait_for("(function(){var a=document.querySelector('.message.own .message-actions'); var cs=getComputedStyle(a); return cs.opacity==='1' && cs.display!=='none';})()",
                   'actions visible on focus-within')

# 2. Enter opens the dialog, focus lands in the textarea.
key('Enter', 'Enter', 13, text='\r')
opened = wait_for(MODAL_OPEN, 'dialog opens on Enter')
focus_textarea = wait_for("document.activeElement && document.activeElement.id === 'editTextarea'",
                          'focus in textarea')

# 3. Tab trap: from the last item (Save) Tab wraps to the first (close button);
#    Shift+Tab from the first wraps back to the last.
ev("(function(){var m=document.getElementById('editModal');var it=[...m.querySelectorAll('button, textarea')].filter(function(e){return !e.disabled && e.offsetParent!==null;}); it[it.length-1].focus(); window.__first=it[0]; window.__last=it[it.length-1]; return it.length;})()")
key('Tab', 'Tab', 9)
tab_fwd = ev("document.activeElement === window.__first")
key('Tab', 'Tab', 9, mods=8)  # Shift+Tab from first wraps to last
tab_back = ev("document.activeElement === window.__last")

# 4. Escape closes and focus returns to the Edit button.
key('Escape', 'Escape', 27)
closed = bool(opened) and wait_for(MODAL_CLOSED, 'dialog closes on Escape')
returned = bool(opened) and wait_for("document.activeElement && document.activeElement.classList.contains('edit-btn')",
                    'focus returns to edit button')

# 5. A real click on the SVG icon inside the Edit button opens the dialog.
#    (The action buttons are type="button": the shared enhanceAccessibility()
#    loading state must not latch onto them and make them unclickable.)
rect = ev("(function(){var s=document.querySelector('.message.own .edit-btn svg'); if(!s) return null; var r=s.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2};})()")
icon_click = False
if rect:
    click_at(rect['x'], rect['y'])
    icon_click = wait_for(MODAL_OPEN, 'dialog opens on icon click')
    ev("if (window.__tc_modal_open_check === undefined) { document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape'})); } 1")
    key('Escape', 'Escape', 27)
    wait_for(MODAL_CLOSED, 'dialog closes after icon-click check', timeout=4)
else:
    errors.append('edit button has no svg icon')

print(json.dumps({
    'seed': seed, 'focused': focused, 'reveals': reveals,
    'enterOpens': opened, 'focusTextarea': focus_textarea,
    'tabWrapsForward': tab_fwd, 'shiftTabWrapsBack': tab_back,
    'escapeCloses': closed, 'focusReturned': returned,
    'iconClickOpens': icon_click, 'errors': errors,
}))
