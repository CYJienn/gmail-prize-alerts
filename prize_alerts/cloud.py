"""Encrypted durable state for ephemeral GitHub runners; never print payloads."""
import base64
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zlib
import requests
from cryptography.fernet import Fernet
from .__main__ import ROOT, lock


def pack_state(root, key):
    with tempfile.TemporaryDirectory() as folder:
        backup=Path(folder)/'backup.sqlite3'
        source=sqlite3.connect(root/'alerts.sqlite3')
        target=sqlite3.connect(backup)
        try: source.backup(target)
        finally: target.close(); source.close()
        payload={'database':base64.b64encode(backup.read_bytes()).decode(), 'token':(root/'token.json').read_text(encoding='utf-8')}
        return Fernet(key).encrypt(zlib.compress(json.dumps(payload).encode()))


def unpack_state(root,key,encrypted):
    payload=json.loads(zlib.decompress(Fernet(key).decrypt(encrypted)))
    data=base64.b64decode(payload['database'],validate=True)
    if not data.startswith(b'SQLite format 3\x00'): raise RuntimeError('Invalid state database.')
    json.loads(payload['token'])
    (root/'alerts.sqlite3').write_bytes(data)
    (root/'token.json').write_text(payload['token'],encoding='utf-8')


class Store:
    def __init__(self):
        self.url='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']
        self.session=requests.Session()
        self.session.headers.update({'Authorization':'Bearer '+os.environ['GH_STATE_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
        self.sha=None
    def request(self,method,path,**kwargs):
        response=self.session.request(method,self.url+path,timeout=(10,60),**kwargs)
        if response.status_code>=400 and response.status_code!=404:
            raise RuntimeError('GitHub state request failed (HTTP '+str(response.status_code)+'). No sensitive details logged.')
        return response
    def restore(self):
        branch=self.request('GET','/git/ref/heads/alert-state')
        if branch.status_code==404:
            return (ROOT/'cloud/initial-state.enc').read_bytes()
        response=self.request('GET','/contents/state.enc?ref=alert-state')
        if response.status_code==404: raise RuntimeError('Existing state branch has no state file; refusing to reset delivery history.')
        value=response.json();self.sha=value['sha']
        return base64.b64decode(value['content'])
    def save(self,encrypted):
        branch=self.request('GET','/git/ref/heads/alert-state')
        if branch.status_code==404:
            repo=self.request('GET','').json()
            head=self.request('GET','/git/ref/heads/'+repo['default_branch']).json()['object']['sha']
            response=self.request('POST','/git/refs',json={'ref':'refs/heads/alert-state','sha':head})
            if response.status_code==404: raise RuntimeError('Could not create state branch.')
        payload={'message':'Save encrypted alert delivery state','branch':'alert-state','content':base64.b64encode(encrypted).decode()}
        if self.sha: payload['sha']=self.sha
        response=self.request('PUT','/contents/state.enc',json=payload)
        if response.status_code==404: raise RuntimeError('Could not save delivery state.')
        print('Encrypted delivery state saved.')


def prepare():
    key_path=ROOT/'.cloud-state-key'
    key=key_path.read_bytes().strip() if key_path.exists() else Fernet.generate_key()
    with lock():
        key_path.write_bytes(key)
        (ROOT/'cloud/initial-state.enc').write_bytes(pack_state(ROOT,key))
    print('Encrypted initial state prepared. Key stays in ignored .cloud-state-key; never paste it into chat.')


def run():
    key=os.environ['STATE_ENCRYPTION_KEY'].encode()
    if not os.getenv('TELEGRAM_BOT_TOKEN') or not os.getenv('TELEGRAM_CHAT_ID'): raise RuntimeError('Required Telegram secrets are missing.')
    store=Store()
    unpack_state(ROOT,key,store.restore())
    # Restore must succeed before scanning; never silently restart from an empty database.
    command=os.environ.get('ALERT_COMMAND','dry-run')
    if command not in ('dry-run','telegram-test','run'): raise RuntimeError('Unsupported cloud command.')
    result=subprocess.run([sys.executable,'-m','prize_alerts',command],cwd=ROOT)
    # Even a partially failed delivery must persist confirmed successes and pending parts.
    store.save(pack_state(ROOT,key))
    if result.returncode: raise RuntimeError('Scanner failed; encrypted pending state saved. See safe scanner error above.')


def replace_token(encrypted, key, token):
    """Replace only authorization; preserve the latest cloud database byte for byte."""
    payload=json.loads(zlib.decompress(Fernet(key).decrypt(encrypted)))
    value=json.loads(token)
    if not value.get('refresh_token'):
        raise RuntimeError('New authorization has no refresh token. Authorize again.')
    if 'database' not in payload:
        raise RuntimeError('Cloud delivery history is missing; refusing migration.')
    payload['token']=token
    return Fernet(key).encrypt(zlib.compress(json.dumps(payload).encode()))


def sync_token():
    from .__main__ import gmail
    gmail()  # Verify student mailbox and read-only scope before uploading.
    result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,timeout=30)
    values=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or not values.get('password'):
        raise RuntimeError('GitHub authentication is required locally.')
    os.environ['GH_STATE_TOKEN']=values['password']
    os.environ['GITHUB_REPOSITORY']='CYJienn/gmail-prize-alerts'
    key=(ROOT/'.cloud-state-key').read_bytes().strip()
    store=Store()
    encrypted=store.restore()
    if not store.sha:
        raise RuntimeError('Existing cloud delivery state was not found; refusing reset.')
    # Optimistic SHA check in save prevents overwriting a concurrent cloud run.
    updated=replace_token(encrypted,key,(ROOT/'token.json').read_text(encoding='utf-8'))
    store.save(updated)
    print('Cloud Gmail authorization updated; delivery history preserved.')

if __name__=='__main__':
    try:
        if len(sys.argv)>1 and sys.argv[1]=='prepare': prepare()
        elif len(sys.argv)>1 and sys.argv[1]=='sync-token': sync_token()
        else: run()
    except Exception as exc:
        print(str(exc) if isinstance(exc,RuntimeError) else 'Cloud operation failed ('+type(exc).__name__+'); sensitive details suppressed.')
        raise SystemExit(1)
