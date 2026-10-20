import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import time
if os.name == 'nt':
    import msvcrt
else:
    import fcntl
import requests
from dotenv import load_dotenv, set_key
from .core import TZ, boundary, eligible, extract, split_text, split_alert

ROOT = Path(__file__).resolve().parent.parent
ACCOUNT = '23118637@siswa.um.edu.my'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

@contextmanager
def lock():
    with open(ROOT/'.run.lock','a+b') as f:
        f.seek(0); f.write(b'0'); f.flush(); f.seek(0)
        try:
            if os.name == 'nt':
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another command is running. Try again when it finishes.')
        try:
            yield
        finally:
            if os.name == 'nt':
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def database(path=None):
    db = sqlite3.connect(path or ROOT/'alerts.sqlite3')
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''CREATE TABLE IF NOT EXISTS windows(start TEXT PRIMARY KEY,end TEXT,complete INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS parts(message TEXT,part INTEGER,text TEXT,sent INTEGER DEFAULT 0,telegram_id INTEGER,PRIMARY KEY(message,part));''')
    return db

def gmail(authorize=False):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    path = ROOT/'token.json'
    creds = None
    if path.exists(): creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if authorize:
        print('Choose ONLY '+ACCOUNT+' in the browser. Approve Gmail read-only access.')
        flow = InstalledAppFlow.from_client_secrets_file(str(ROOT/'credentials.json'),SCOPES)
        creds = flow.run_local_server(port=0,open_browser=True,authorization_prompt_message='Opening Google sign-in in your browser.',prompt='consent',login_hint=ACCOUNT)
    elif creds and creds.expired and creds.refresh_token: creds.refresh(Request())
    if not creds or not creds.valid: raise RuntimeError('Run the authorize command first. Expired/revoked tokens require authorizing again.')
    if set(creds.scopes or []) != set(SCOPES): raise RuntimeError('Unexpected OAuth scopes. Remove token.json locally and authorize with this project.')
    service = build('gmail','v1',credentials=creds,cache_discovery=False)
    profile = service.users().getProfile(userId='me').execute(num_retries=4)
    if profile['emailAddress'].lower()!=ACCOUNT: raise RuntimeError('Wrong mailbox authorized. Delete token.json locally and authorize using '+ACCOUNT)
    path.write_text(creds.to_json(),encoding='utf-8')
    return service

def telegram(method, payload, attempts=5):
    token=os.getenv('TELEGRAM_BOT_TOKEN','')
    if not token or token=='replace_locally': raise RuntimeError('Enter TELEGRAM_BOT_TOKEN in the local .env file first.')
    for attempt in range(attempts):
        try:
            response=requests.post('https://api.telegram.org/bot'+token+'/'+method,json=payload,timeout=(10,45))
            data=response.json()
        except (requests.RequestException,ValueError):
            if attempt==attempts-1: raise RuntimeError('Telegram network failure; delivery may be ambiguous. Retry later (a duplicate is possible).') from None
            time.sleep(2**attempt); continue
        if data.get('ok'): return data['result']
        code=data.get('error_code',response.status_code)
        if code==429 or code>=500:
            time.sleep(max(1,data.get('parameters',{}).get('retry_after',2**attempt))); continue
        raise RuntimeError(f'Telegram rejected request (code {code}). Check bot token, private chat and whether bot is blocked.')
    raise RuntimeError('Telegram temporary failure after retries; pending deliveries retained.')

def private_chat():
    cid=os.getenv('TELEGRAM_CHAT_ID','')
    if not cid.isdigit(): raise RuntimeError('Run telegram-setup to configure a private chat ID.')
    chat=telegram('getChat',{'chat_id':cid})
    if chat['type']!='private': raise RuntimeError('Configured Telegram chat must be private.')
    return cid

def deliver(db, send):
    for mid,part,text in db.execute('SELECT message,part,text FROM parts WHERE sent=0 ORDER BY rowid').fetchall():
        result=send(text)
        db.execute('UPDATE parts SET sent=1,telegram_id=? WHERE message=? AND part=?',(result['message_id'],mid,part)); db.commit()
        time.sleep(1.1)

def scan(service,db,start,end,dry=False,record_window=True):
    page=None; count=0
    while True:
        response=service.users().messages().list(userId='me',q=f'after:{int(start.timestamp())-1} before:{int(end.timestamp())+1} -in:spam -in:trash -in:drafts',includeSpamTrash=False,maxResults=500,pageToken=page).execute(num_retries=4)
        for item in response.get('messages',[]):
            msg=service.users().messages().get(userId='me',id=item['id'],format='raw').execute(num_retries=4)
            if not eligible(msg,start,end): continue
            text=extract(base64.urlsafe_b64decode(msg['raw']), msg['internalDate'])
            if text is None: continue
            count+=1
            if not dry:
                for i,part in enumerate(split_alert(text)):
                    db.execute('INSERT OR IGNORE INTO parts(message,part,text) VALUES(?,?,?)',(item['id'],i,part))
        page=response.get('nextPageToken')
        if not page: break
    if not dry:
        if record_window: db.execute('INSERT OR REPLACE INTO windows VALUES(?,?,1)',(start.isoformat(),end.isoformat()))
        db.commit()
    print(f'Window {start.isoformat()} to {end.isoformat()}: {count} matching messages'+(' (dry-run; no content stored or sent)' if dry else ' queued.'))

def main():
    parser=argparse.ArgumentParser(description='Local Gmail prize alerts')
    parser.add_argument('command',choices=['authorize','telegram-setup','telegram-test','dry-run','run','recover','status'])
    parser.add_argument('--chat-id',help='Explicit private chat selection for telegram-setup')
    parser.add_argument('--start',help='Inclusive ISO timestamp with offset, paired with --end')
    parser.add_argument('--end',help='Exclusive ISO timestamp with offset')
    args=parser.parse_args(); load_dotenv(ROOT/'.env')
    with lock():
        if args.command=='authorize': gmail(True); print('Verified authorized mailbox: '+ACCOUNT); return
        if args.command=='telegram-setup':
            updates=telegram('getUpdates',{'timeout':0,'allowed_updates':['message']})
            chats={str(u['message']['chat']['id']) for u in updates if 'message' in u and u['message']['chat']['type']=='private'}
            if not chats: raise RuntimeError('Open your bot in Telegram, press Start, send hello, then run telegram-setup again. Updates expire after 24 hours.')
            if args.chat_id:
                if args.chat_id not in chats: raise RuntimeError('Selected ID was not in recent private messages.')
                chosen=args.chat_id
            elif len(chats)==1: chosen=next(iter(chats))
            else: print('Multiple private chats. Rerun with --chat-id and one of: '+', '.join(sorted(chats))); return
            set_key(str(ROOT/'.env'),'TELEGRAM_CHAT_ID',chosen); print('Saved private chat ID locally. Run telegram-test next.'); return
        if args.command=='telegram-test':
            cid=private_chat(); telegram('sendMessage',{'chat_id':cid,'text':'Gmail Prize Alerts test: private Telegram delivery is working.','link_preview_options':{'is_disabled':True}}); print('Test notification sent.'); return
        db=database()
        try:
            if args.command=='status':
                print('Completed windows:',db.execute('SELECT count(*) FROM windows WHERE complete=1').fetchone()[0]); print('Pending parts:',db.execute('SELECT count(*) FROM parts WHERE sent=0').fetchone()[0]); return
            if args.command!='recover':
                service=gmail(); latest=boundary()
                if bool(args.start)!=bool(args.end): raise RuntimeError('Supply both --start and --end.')
                if args.start:
                    start,end=datetime.fromisoformat(args.start),datetime.fromisoformat(args.end)
                    if start.tzinfo is None or end.tzinfo is None or start>=end: raise RuntimeError('Use ordered timestamps with timezone offsets.')
                    scan(service,db,start,end,args.command=='dry-run',record_window=False)
                else:
                    # Persist the first intended window before network work; resume it after failures.
                    row=db.execute('SELECT MIN(start) FROM windows').fetchone()[0]
                    start=datetime.fromisoformat(row) if row else latest-timedelta(days=1)
                    while start<latest:
                        end=start+timedelta(days=1)
                        done=db.execute('SELECT complete FROM windows WHERE start=?',(start.isoformat(),)).fetchone()
                        if args.command=='dry-run' or not done or not done[0]:
                            if args.command!='dry-run':
                                db.execute('INSERT OR IGNORE INTO windows(start,end) VALUES(?,?)',(start.isoformat(),end.isoformat())); db.commit()
                            scan(service,db,start,end,args.command=='dry-run')
                        start=end
            if args.command in ('run','recover'):
                if db.execute('SELECT 1 FROM parts WHERE sent=0 LIMIT 1').fetchone():
                    cid=private_chat()
                    deliver(db,lambda text:telegram('sendMessage',{'chat_id':cid,'text':text,'link_preview_options':{'is_disabled':True}}))
                print('All queued deliveries complete.')
        finally: db.close()

if __name__=='__main__':
    try: main()
    except Exception as exc:
        # Third-party exception strings may contain tokens, URLs, or email content.
        print(str(exc) if isinstance(exc,RuntimeError) else 'Operation failed ('+type(exc).__name__+'). Check configuration, connectivity, OAuth consent or university policy. No sensitive error details printed.')
        raise SystemExit(1)
