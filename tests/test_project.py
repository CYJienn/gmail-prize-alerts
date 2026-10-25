from datetime import datetime, timedelta
from email.message import EmailMessage
import pytest
from prize_alerts.core import *
from prize_alerts.__main__ import database, deliver, scan

def email(body,subject='Announcement',html=False):
    m=EmailMessage(); m['Subject']=subject; m['From']='Office <office@example.org>'
    m.set_content(body,subtype='html' if html else 'plain'); return m.as_bytes()

@pytest.mark.parametrize('word,match',[('PRIZE',True),('prizes',True),('surprize',False),('prized',False),('prizewinning',False)])
def test_words(word,match): assert bool(extract(email(word)))==match

def test_boundary():
    assert boundary(datetime(2026,10,21,7,59,tzinfo=TZ))==datetime(2026,10,20,8,tzinfo=TZ)
    assert boundary(datetime(2026,10,21,8,tzinfo=TZ))==datetime(2026,10,21,8,tzinfo=TZ)

def test_individual():
    a=datetime(2026,10,20,8,tzinfo=TZ); b=a+timedelta(days=1)
    for labels,want in [([],True),(['UNREAD'],True),(['SPAM'],False),(['TRASH'],False),(['DRAFT'],False),(['SENT'],False)]:
        assert eligible({'labelIds':labels,'internalDate':str(int(a.timestamp()*1000))},a,b)==want
    assert not eligible({'internalDate':int(b.timestamp()*1000)},a,b)

def test_plain_exact():
    result=extract(email('Win prizes!\n\nRegister here https://example.org/apply?a=1&utm_source=uni#form'))
    assert 'Register here https://example.org/apply?a=1&utm_source=uni#form' in result
    assert 'Office <office@example.org>' in result

def test_html():
    result=extract(email('<p>Win a prize!</p><p><a href="https://example.org/?x=1&amp;y=2">Register now</a></p><a href="https://example.org/unsubscribe">Unsubscribe</a>',html=True))
    assert 'https://example.org/?x=1&y=2' in result
    assert 'https://example.org/unsubscribe' not in result

def test_fallback(): assert "Cannot extract the participation link. Please check Gmail: 'Prize offer'." in extract(email('Details soon','Prize offer'))

def test_split():
    value='😀'*5000+'https://example.org/?'+('x'*10000)
    parts=split_text(value)
    assert ''.join(parts)==value
    assert all(len(p.encode('utf-16-le'))//2<=3900 for p in parts)

def test_recovery(tmp_path,monkeypatch):
    monkeypatch.setattr('prize_alerts.__main__.time.sleep',lambda _:None)
    db=database(tmp_path/'test.sqlite3')
    db.executemany('INSERT INTO parts(message,part,text) VALUES(?,?,?)',[('a',0,'first'),('a',1,'second')]); db.commit()
    calls=[]
    def fail(text):
        calls.append(text)
        if text=='second': raise RuntimeError('temporary')
        return {'message_id':1}
    with pytest.raises(RuntimeError): deliver(db,fail)
    assert db.execute('SELECT sent FROM parts ORDER BY part').fetchall()==[(1,),(0,)]
    deliver(db,lambda text:calls.append(text) or {'message_id':2})
    deliver(db,lambda text:pytest.fail('duplicate'))
    assert calls==['first','second','second']

def test_scan_pagination(tmp_path):
    import base64
    a=datetime(2026,10,20,8,tzinfo=TZ); b=a+timedelta(days=1)
    class Fake:
        def users(self): return self
        def messages(self): return self
        def list(self,**kw): self.page=kw['pageToken']; return self
        def get(self,**kw): self.mid=kw['id']; return self
        def execute(self,**kw):
            if hasattr(self,'mid'):
                mid=self.mid; del self.mid
                return {'internalDate':int(a.timestamp()*1000),'labelIds':[], 'raw':base64.urlsafe_b64encode(email('prize' if mid=='a' else 'ordinary notice')).decode()}
            return {'messages':[{'id':'b'}]} if self.page else {'messages':[{'id':'a'}],'nextPageToken':'next'}
    db=database(tmp_path/'test.sqlite3'); scan(Fake(),db,a,b)
    assert db.execute('SELECT DISTINCT message FROM parts').fetchall()==[('a',)]
    assert db.execute('SELECT complete FROM windows').fetchone()==(1,)

@pytest.mark.parametrize('word,match',[('WIN',True),('Win!',True),('win',True),('window',False),('winning',False),('twin',False)])
def test_win_words(word,match):
    assert bool(extract(email(word))) == match

def test_win_subject_and_original_excerpt():
    assert extract(email('Details soon', 'Win a voucher')) is not None
    result = extract(email('Win a voucher!\n\nRegister https://example.org/?a=1&utm_source=test'))
    assert 'Win a voucher!' in result
    assert 'https://example.org/?a=1&utm_source=test' in result


def test_sent_date_malaysia_each_part():
    m=EmailMessage(); m['Subject']='Win'; m['Date']='Tue, 20 Oct 2026 08:11:00 +0000'
    m.set_content('Win '+('details '*1500))
    result=extract(m.as_bytes())
    assert result.endswith('Sent: Tue, Oct 20, 4:11 PM (Malaysia time)')
    parts=split_alert(result)
    assert len(parts)>1
    assert all(p.endswith('Sent: Tue, Oct 20, 4:11 PM (Malaysia time)') for p in parts)
    assert all(len(p.encode('utf-16-le'))//2<=3900 for p in parts)

def test_missing_sent_date_uses_received():
    received=datetime(2026,10,20,16,11,tzinfo=TZ)
    result=extract(email('Win'),int(received.timestamp()*1000))
    assert result.endswith('Received (sent date unavailable): Tue, Oct 20, 4:11 PM (Malaysia time)')


def test_mailing_list_delivery_timestamp():
    m=EmailMessage(); m['Subject']='Win'
    m['Date']='Tue, 20 Oct 2026 13:18:38 +0800'
    m['Received']='by final.example; Tue, 20 Oct 2026 01:11:17 -0700 (PDT)'
    m['Received']='by earlier.example; Mon, 19 Oct 2026 22:19:02 -0700 (PDT)'
    m.set_content('Win '+('details '*1500))
    result=extract(m.as_bytes(),int(datetime(2026,10,20,13,18,tzinfo=TZ).timestamp()*1000))
    assert result.endswith('Sent: Tue, Oct 20, 1:18 PM (Malaysia time)')
    assert all(part.endswith('Sent: Tue, Oct 20, 1:18 PM (Malaysia time)') for part in split_alert(result))

def test_invalid_received_header_falls_back():
    m=EmailMessage(); m['Subject']='Win'; m['Date']='Tue, 20 Oct 2026 13:18:38 +0800'
    m['Received']='invalid'; m.set_content('Win')
    assert extract(m.as_bytes()).endswith('Sent: Tue, Oct 20, 1:18 PM (Malaysia time)')


@pytest.mark.parametrize('date,expected',[
    ('Tue, 20 Oct 2026 13:15:29 +0800', 'Tue, Oct 20, 1:15 PM'),
    ('Tue, 20 Oct 2026 13:18:38 +0800', 'Tue, Oct 20, 1:18 PM'),
    ('Wed, 21 Oct 2026 01:02:00 +0000', 'Wed, Oct 21, 9:02 AM'),
])
def test_timestamp_is_dynamic(date,expected):
    m=EmailMessage(); m['Subject']='Win'; m['Date']=date; m.set_content('Win')
    assert extract(m.as_bytes()).endswith('Sent: '+expected+' (Malaysia time)')


@pytest.mark.parametrize('word', ['competition','COMPETITIONS','Competition!','pertandingan','PERTANDINGAN'])
@pytest.mark.parametrize('location', ['subject','plain','html'])
def test_additional_competition_keywords(word, location):
    if location == 'subject':
        result=extract(email('Details soon',subject=word))
    elif location == 'html':
        result=extract(email('<p>'+word+'</p><p><a href="https://example.org/enter?a=1&amp;utm_source=uni">Register</a></p>',html=True))
        assert 'https://example.org/enter?a=1&utm_source=uni' in result
    else:
        result=extract(email(word+'\n\nRegister https://example.org/enter?a=1&utm_source=uni'))
        assert word in result
        assert 'https://example.org/enter?a=1&utm_source=uni' in result
    assert result is not None

@pytest.mark.parametrize('word', ['competitionish','precompetition','noncompetitions','pertandingannya','prapertandingan'])
def test_additional_keywords_keep_whole_word_boundaries(word):
    assert extract(email(word)) is None
