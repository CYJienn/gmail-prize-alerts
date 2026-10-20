import json
import sqlite3
import pytest
from cryptography.fernet import Fernet, InvalidToken
from prize_alerts.cloud import pack_state, unpack_state
from prize_alerts.__main__ import database, lock

def test_cloud_state_roundtrip(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    target=tmp_path/'target'; target.mkdir()
    db=database(source/'alerts.sqlite3')
    db.execute('INSERT INTO parts(message,part,text,sent) VALUES(?,?,?,?)',('m',0,'private excerpt',1))
    db.execute('INSERT INTO parts(message,part,text,sent) VALUES(?,?,?,?)',('m',1,'pending excerpt',0))
    db.commit()
    (source/'token.json').write_text(json.dumps({'refresh_token':'offline-test-only'}))
    key=Fernet.generate_key(); encrypted=pack_state(source,key)
    assert b'private excerpt' not in encrypted
    assert b'offline-test-only' not in encrypted
    unpack_state(target,key,encrypted)
    restored=sqlite3.connect(target/'alerts.sqlite3')
    assert restored.execute('SELECT sent FROM parts ORDER BY part').fetchall()==[(1,),(0,)]
    assert json.loads((target/'token.json').read_text())['refresh_token']=='offline-test-only'
    restored.close(); db.close()
    with pytest.raises(InvalidToken): unpack_state(target,Fernet.generate_key(),encrypted)

def test_lock_rejects_overlap():
    with lock():
        with pytest.raises(RuntimeError,match='Another command'):
            with lock(): pass
