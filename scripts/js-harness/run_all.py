"""Run every js-harness scenario and enforce its pass criteria.

Requires: local runserver with fixtures (setup_fixtures.py) and headless
Chrome on the CDP port. Exits non-zero if any scenario fails.

    python scripts/js-harness/run_all.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def last_json(output):
    """Extract the first {...} JSON object in the output."""
    m = re.search(r'\{.*\}', output, re.S)
    return json.loads(m.group(0)) if m else {}


def check_quickcall_async_races(out):
    ok = ('A: orphan cancel POST: True' in out
          and 'A: visible error toast: False' in out
          and 'C declined exception: False' in out
          and 'C expired exception: False' in out
          and 'C accepted exception: False' in out)
    return ok, 'orphan cancel POST issued, no error toast, no late-event exceptions'


def check_incoming_call_message_chip(out):
    m = re.search(r'navigated to match \d+\s*:\s*(True|False)', out)
    return bool(m and m.group(1) == 'True'), 'Message chip navigates to the match chat'


def check_user_left_timer(out):
    d = last_json(out)
    ok = 'setup: armed' in out and d.get('timerCleared') is True and d.get('t1') == d.get('t2') == '00:00' and d.get('isCallActive') is False
    return ok, 'timer stopped/reset after abrupt partner leave'


def check_typing_ws_guard(out):
    d = last_json(out)
    ok = d.get('readyState') == 0 and d.get('handleTyping_threw') is None and d.get('stopTyping_threw') is None
    return ok, 'no InvalidStateError typing on a CONNECTING socket'


def check_mid_negotiation_teardown(out):
    d = last_json(out)
    ok = 'messages' in d and d.get('messages') == [] and d.get('wsSent') == 0
    return ok, 'quiet bail on mid-await teardown (no error message, no answer)'


def check_teardown_identity_guard(out):
    d = last_json(out)
    if not d: return False, 'scenario produced no result JSON'
    a, b, c = d.get('A_realTeardown', {}), d.get('B_replacement', {}), d.get('C_happy', {})
    ok = (a.get('messages') == [] and a.get('answersSent') == 0
          and b.get('answersSent') == 0 and b.get('newCreateAnswerCalls') == 0
          and c.get('answersSent') == 1 and c.get('isCallActive') is True)
    return ok, 'real-path teardown bails, replacement untouched, happy path intact'


SCENARIOS = [
    ('quickcall_async_races.py', check_quickcall_async_races),
    ('incoming_call_message_chip.py', check_incoming_call_message_chip),
    ('user_left_timer.py', check_user_left_timer),
    ('typing_ws_guard.py', check_typing_ws_guard),
    ('mid_negotiation_teardown.py', check_mid_negotiation_teardown),
    ('teardown_identity_guard.py', check_teardown_identity_guard),
]


def main():
    failures = 0
    for script, check in SCENARIOS:
        proc = subprocess.run([sys.executable, str(HERE / script)],
                              capture_output=True, text=True, timeout=120)
        out = proc.stdout + proc.stderr
        if proc.returncode != 0:
            print(f'FAIL {script}: exited {proc.returncode}\n{out[-800:]}')
            failures += 1
            continue
        ok, desc = check(out)
        print(f'{"PASS" if ok else "FAIL"} {script}: {desc}')
        if not ok:
            print(out[-800:])
            failures += 1
    print(f'{len(SCENARIOS) - failures}/{len(SCENARIOS)} scenarios passed')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
