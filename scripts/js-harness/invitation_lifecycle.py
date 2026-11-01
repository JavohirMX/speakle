"""Full call-invitation lifecycle against the real server: two isolated
browser contexts (caller + receiver). Covers send -> receiver modal,
caller cancel -> receiver modal closes + toast, send again -> receiver
decline -> caller toast. These paths were previously only reviewed in
code, never exercised end-to-end in the browser.

Leaves cancelled/declined CallInvitation rows in the fixture DB (the
pending filter ignores them); CI runs against a fresh database.
"""
import json, os, socket, subprocess, sys, time, urllib.request
from websocket import create_connection

import os as _os, json as _json
try:
    _fx = _json.load(open(_os.path.join(_os.path.dirname(__file__), 'fixtures.json')))
except Exception:
    _fx = {}
CDP = _fx.get('cdp_url', 'http://127.0.0.1:9223')
FXU = _fx.get('user', 'a11ydemo'); FXP = _fx.get('password', 'fixture-pass-123')
FXPARTNER = _fx.get('partner', 'fixturepartner'); FXM = _fx.get('match_id', 2)

errors = []

# runserver serves WSGI here (channels' override does not win with this
# INSTALLED_APPS order), so /ws/notifications/ 404s. This scenario needs a
# live notification socket: bring up daphne on its own port against the
# same fixture database and drive both pages there. Static files 404 under
# daphne; the assertions below are classList/DOM-text based and do not
# depend on stylesheet loading.
REPO = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
ASGI_PORT = 8001
BASE = 'http://127.0.0.1:%d' % ASGI_PORT
env = dict(os.environ, SECRET_KEY=os.environ.get('SECRET_KEY', 'devsecret'),
           DEBUG=os.environ.get('DEBUG', 'True'))
daphne = subprocess.Popen(
    [sys.executable, '-m', 'daphne', '-b', '127.0.0.1', '-p', str(ASGI_PORT),
     'config.asgi:application'],
    cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try:
        socket.create_connection(('127.0.0.1', ASGI_PORT), timeout=1).close(); break
    except OSError:
        if daphne.poll() is not None:
            raise Exception('daphne exited early with code %s' % daphne.returncode)
        time.sleep(0.2)
else:
    raise Exception('daphne did not start listening on %d' % ASGI_PORT)

def page_ws(target_id=None):
    ts = json.load(urllib.request.urlopen(CDP + '/json'))
    for x in ts:
        if x.get('type') == 'page' and (target_id is None or x.get('id') == target_id):
            return x['webSocketDebuggerUrl']
    raise Exception('page target not found: %r' % target_id)

class Tab:
    def __init__(self, wsurl):
        self.ws = create_connection(wsurl, timeout=60); self.mid = [0]
    def cmd(self, m, **p):
        self.mid[0] += 1
        self.ws.send(json.dumps({'id': self.mid[0], 'method': m, 'params': p}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get('id') == self.mid[0]:
                if 'error' in r: raise Exception(r['error'])
                return r.get('result', {})
    def evraw(self, e):
        return self.cmd('Runtime.evaluate', expression=e, returnByValue=True, awaitPromise=True)
    def ev(self, e):
        return self.evraw(e).get('result', {}).get('value')
    def login(self, username):
        self.cmd('Page.navigate', url=BASE + '/users/login/'); time.sleep(2)
        r = self.evraw("var u=document.getElementById('id_username'); u.value='" + username +
                "'; document.getElementById('id_password').value='" + FXP +
                "'; u.closest('form').submit(); 1")
        if 'exceptionDetails' in r:
            errors.append('login submit threw for %s: %s' % (username, r['exceptionDetails'].get('text')))
        time.sleep(3)
        self.cmd('Page.navigate', url=BASE + '/'); time.sleep(3)
        st = self.ev("fetch('/chats/api/pending-invitations/').then(r=>r.status)")
        if st != 200:
            errors.append('%s not authenticated after login (status %r, url %s)'
                          % (username, st, self.ev('location.href')))
    def post(self, path):
        return self.ev("""(async function(){
          var csrf=(document.cookie.split('; ').find(function(r){return r.startsWith('csrftoken=')})||'=').split('=')[1];
          var r=await fetch('""" + path + """',{method:'POST',headers:{'X-CSRFToken':csrf}});
          var t=await r.text(); var d=null; try{d=JSON.parse(t);}catch(e){}
          return {status:r.status, body:d||t};})()""")
    def wait_for(self, expr, label, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if self.ev(expr): return True
            time.sleep(0.5)
        errors.append('timeout waiting for ' + label)
        return False

MODAL_VISIBLE = "(function(){var m=document.getElementById('globalIncomingCallModal');return !!m&&!m.classList.contains('hidden');})()"
MODAL_HIDDEN = "(function(){var m=document.getElementById('globalIncomingCallModal');return !m||m.classList.contains('hidden');})()"
def toast_seen(text):
    return ("!![...document.querySelectorAll('body *')].find(function(d){var s=getComputedStyle(d);"
            "return d.children.length===0&&s.display!=='none'&&s.visibility!=='hidden'&&"
            "d.textContent.indexOf('" + text + "')>=0;})")

# Bind the caller tab BEFORE creating the receiver target: /json ordering is
# not stable, so picking 'the first page' after creating the second target can
# bind both tabs to the same page and silently collapse the two sessions into
# one cookie context.
caller_ws_url = page_ws()
# Receiver: isolated browser context so its session cookie does not clobber the caller's.
bver = json.load(urllib.request.urlopen(CDP + '/json/version'))
bws = create_connection(bver['webSocketDebuggerUrl'], timeout=60); bmid = [0]
def bcmd(m, **p):
    bmid[0] += 1
    bws.send(json.dumps({'id': bmid[0], 'method': m, 'params': p}))
    while True:
        r = json.loads(bws.recv())
        if r.get('id') == bmid[0]:
            if 'error' in r: raise Exception(r['error'])
            return r.get('result', {})
ctx = bcmd('Target.createBrowserContext')['browserContextId']
tid = bcmd('Target.createTarget', url='about:blank', browserContextId=ctx)['targetId']
time.sleep(1)

caller = Tab(caller_ws_url)      # existing page, default context
receiver = Tab(page_ws(tid))     # new page, isolated context
# Clear any stale session before either login (clears browser-wide, so it
# must run before the receiver context logs in, not between the logins).
caller.cmd('Network.enable'); caller.cmd('Network.clearBrowserCookies')
caller.cmd('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)
receiver.cmd('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)

caller.login(FXU)                # a11ydemo
receiver.login(FXPARTNER)        # fixturepartner; page load flips presence online via middleware

# The notification socket must be genuinely OPEN: the page also shows the
# incoming-call modal from the pending-invitations poll, which would mask a
# dead socket and skip every ws-only path this scenario exists to cover.
WS_OPEN = ("(typeof globalNotificationSocket !== 'undefined' && globalNotificationSocket "
           "&& globalNotificationSocket.readyState) === 1")
ws_caller = caller.wait_for(WS_OPEN, 'caller notification ws OPEN')
ws_receiver = receiver.wait_for(WS_OPEN, 'receiver notification ws OPEN')
if not (ws_caller and ws_receiver):
    errors.append('ws readyState diag: caller=%r receiver=%r' % (
        caller.ev("typeof globalNotificationSocket !== 'undefined' && globalNotificationSocket ? globalNotificationSocket.readyState : null"),
        receiver.ev("typeof globalNotificationSocket !== 'undefined' && globalNotificationSocket ? globalNotificationSocket.readyState : null")))

# --- Round 1: send -> receiver modal -> caller cancels -> modal closes + toast
r1 = caller.post('/chats/api/send-invitation/%d/' % FXM)
send1 = isinstance(r1.get('body'), dict) and r1['body'].get('success') is True
if not send1: errors.append('send1 failed: %r' % r1)
inv1 = r1.get('body', {}).get('invitation_id') if isinstance(r1.get('body'), dict) else None
modal1 = receiver.wait_for(MODAL_VISIBLE, 'modal on send')
caller_name_seen = receiver.ev("document.getElementById('globalCallerName').textContent.trim()")
name_ok = caller_name_seen == FXU
if not name_ok: errors.append('caller name wrong in modal: %r' % caller_name_seen)
cancel1 = caller.post('/chats/api/cancel-invitation/%d/' % inv1)['body'] if inv1 else {}
hidden_after_cancel = receiver.wait_for(MODAL_HIDDEN, 'modal hidden after cancel')
cancel_toast = receiver.wait_for(toast_seen('cancelled the call'), 'cancel toast')

# --- Round 2: send again -> receiver declines -> caller toast
r2 = caller.post('/chats/api/send-invitation/%d/' % FXM)
send2 = isinstance(r2.get('body'), dict) and r2['body'].get('success') is True
if not send2: errors.append('send2 failed: %r' % r2)
modal2 = receiver.wait_for(MODAL_VISIBLE, 'modal on resend')
receiver.ev('globalDeclineCall(); 1')
decline_toast = caller.wait_for(toast_seen('declined your call'), 'decline toast on caller')

bcmd('Target.closeTarget', targetId=tid)
bcmd('Target.disposeBrowserContext', browserContextId=ctx)
daphne.terminate()
try:
    daphne.wait(timeout=10)
except Exception:
    daphne.kill()
print(json.dumps({
    'wsCallerOpen': ws_caller, 'wsReceiverOpen': ws_receiver,
    'send1': send1, 'modalShown1': modal1, 'callerNameOk': name_ok,
    'cancelOk': cancel1.get('success') is True,
    'modalHiddenAfterCancel': hidden_after_cancel, 'cancelToast': cancel_toast,
    'send2': send2, 'modalShown2': modal2, 'declineToast': decline_toast,
    'errors': errors,
}))
