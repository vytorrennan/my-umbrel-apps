#!/usr/bin/env python3
"""Start idle five-hour Codex windows with GPT-6 Luna low only."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import select
import subprocess
import time

ROOT = Path.home() / '.local/share/codex-window-starter'
STATE = ROOT / 'state.json'
CODEX = '/home/developer/.npm-global/bin/codex'
MODEL = 'gpt-6-luna'
BUFFER = 60


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), message, flush=True)


class Server:
    def __enter__(self):
        self.seq = 0
        self.buffer = b''
        self.p = subprocess.Popen([CODEX, 'app-server'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  cwd=ROOT / 'empty', start_new_session=True)
        self.call('initialize', {'clientInfo': {'name': 'window-starter', 'version': '1.0'}})
        self.send({'method': 'initialized'})
        return self

    def __exit__(self, *args):
        self.p.terminate()
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()

    def send(self, message):
        self.p.stdin.write((json.dumps(message) + '\n').encode())
        self.p.stdin.flush()

    def receive(self, deadline):
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.p.stdout], [], [], remaining)[0]:
                raise TimeoutError('Codex response timed out')
            data = os.read(self.p.stdout.fileno(), 65536)
            if not data:
                raise RuntimeError('Codex server exited')
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)

    def call(self, method, params=None):
        self.seq += 1
        request_id = self.seq
        self.send({'id': request_id, 'method': method, 'params': params or {}})
        deadline = time.monotonic() + 45
        while True:
            message = self.receive(deadline)
            if message.get('id') == request_id:
                if 'error' in message:
                    raise RuntimeError(method + ' failed: ' + str(message['error'].get('message')))
                return message['result']

    def limits(self):
        result = self.call('account/rateLimits/read')
        bucket = result.get('rateLimitsByLimitId', {}).get('codex') or result.get('rateLimits')
        if not bucket or bucket.get('primary', {}).get('windowDurationMins') != 300:
            raise RuntimeError('No recognizable five-hour Codex allowance; no message sent')
        return bucket, result.get('ordinaryUsageAllowed', True)

    def ping(self):
        models = self.call('model/list', {'includeHidden': True})['data']
        model = next((m for m in models if m['model'] == MODEL), None)
        efforts = [x['reasoningEffort'] for x in (model or {}).get('supportedReasoningEfforts', [])]
        if not model or 'low' not in efforts:
            raise RuntimeError('GPT-6 Luna low unavailable; no fallback model permitted')
        # Disable skills for this thread only, without changing normal Codex settings.
        skills = []
        for folder in [Path.home() / '.agents/skills', Path.home() / '.codex/skills']:
            for path in folder.rglob('SKILL.md'):
                skills.append({'path': str(path), 'enabled': False})
        started = self.call('thread/start', {
            'model': MODEL, 'modelProvider': 'openai', 'ephemeral': True,
            'cwd': str(ROOT / 'empty'), 'approvalPolicy': 'never', 'sandbox': 'read-only',
            'baseInstructions': 'Reply to the user with OK. Do not use any tools.',
            'developerInstructions': 'Reply only with OK.',
            'config': {'model_reasoning_effort': 'low', 'web_search': 'disabled',
                       'features': {'multi_agent': False, 'shell_tool': False},
                       'skills': {'config': skills}},
        })
        if started.get('model') != MODEL:
            raise RuntimeError('Unexpected selected model; no turn started')
        thread_id = started['thread']['id']
        self.call('turn/start', {'threadId': thread_id, 'model': MODEL, 'effort': 'low',
                                'input': [{'type': 'text', 'text': 'Reply only with OK.',
                                           'text_elements': []}]})
        deadline = time.monotonic() + 120
        answer = None
        usage = None
        while True:
            message = self.receive(deadline)
            method = message.get('method')
            params = message.get('params', {})
            if method == 'thread/tokenUsage/updated':
                usage = params.get('tokenUsage')
            if method == 'item/completed':
                item = params.get('item', {})
                if item.get('type') == 'agentMessage':
                    answer = item.get('text')
                elif item.get('type') in ['commandExecution', 'mcpToolCall', 'webSearch', 'fileChange']:
                    raise RuntimeError('Unexpected tool activity; stopping run')
            if method == 'turn/completed':
                if params['turn']['status'] != 'completed' or answer != 'OK':
                    raise RuntimeError('Tiny message did not complete with OK')
                log('GPT-6 Luna low returned OK; token usage=' + json.dumps(usage))
                return


def decision(bucket, allowed, state, now):
    secondary = bucket.get('secondary') or {}
    if not allowed or (secondary.get('usedPercent', 0) >= 100 and secondary.get('resetsAt', 0) > now):
        return False, 300, 'Allowance unavailable; waiting without sending'
    reset = bucket['primary'].get('resetsAt')
    if reset is None:
        raise RuntimeError('Missing reset timestamp; no message sent')
    # Idle-window reads can synthesize a reset at now + five hours. Preserve
    # our deadline instead of chasing that moving timestamp on every poll.
    if 'next_due' not in state:
        state['next_due'] = (state['last_success'] + 300 * 60 + BUFFER
                             if state.get('last_success') else reset + BUFFER)
    due = state['next_due']
    if now < due:
        return False, min(300, max(1, due - now)), 'Next eligible message at ' + time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(due))
    return True, 1, 'Saved deadline reached; sending window-start message'


def save(state):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state) + '\n')
    tmp.replace(STATE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Read limits only, then exit')
    parser.add_argument('--test-ping', action='store_true', help='Send one validation message')
    args = parser.parse_args()
    ROOT.joinpath('empty').mkdir(exist_ok=True)
    lock = open(ROOT / 'lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    while True:
        try:
            with Server() as server:
                bucket, allowed = server.limits()
                send, delay, reason = decision(bucket, allowed, state, time.time())
                log(reason)
                if args.check:
                    log('Model fixed to gpt-6-luna; reasoning fixed to low')
                    return
                save(state)
                if args.test_ping or send:
                    if not allowed:
                        raise RuntimeError('Ordinary usage unavailable; no message sent')
                    server.ping()
                    state['last_success'] = time.time()
                    state['next_due'] = state['last_success'] + 300 * 60 + BUFFER
                    state.pop('previous_reset', None)
                    save(state)
                    delay = 300
                if args.test_ping:
                    return
        except Exception as error:
            log('Error: ' + str(error))
            if args.check or args.test_ping:
                raise
            delay = 300
        time.sleep(delay)


if __name__ == '__main__':
    main()
