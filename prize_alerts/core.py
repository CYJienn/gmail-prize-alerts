import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from email import policy
from email.utils import parsedate_to_datetime
from email.parser import BytesParser
from bs4 import BeautifulSoup

TZ = ZoneInfo('Asia/Kuala_Lumpur')
KEY = re.compile(r'\b(?:prizes?|win)\b', re.I)
INSTRUCTION = re.compile(r'\b(register|registration|participat\w*|apply|application|submit|submission|enter|entry|deadline|eligib\w*|competition|contest|join|sign\s*up)\b', re.I)
FOOTER = re.compile(r'unsubscribe|privacy[ -]?policy|facebook\.com|instagram\.com|twitter\.com|linkedin\.com|youtube\.com|manage preferences', re.I)
URL = re.compile(r'https?://[^\s<>"\u200b]+', re.I)

def boundary(now=None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    end = now.replace(hour=8, minute=0, second=0, microsecond=0)
    return end if now >= end else end-timedelta(days=1)

def eligible(message, start, end):
    labels = set(message.get('labelIds', []))
    return not labels.intersection({'SPAM','TRASH','DRAFT'}) and not ('SENT' in labels and 'INBOX' not in labels) and int(start.timestamp()*1000) <= int(message['internalDate']) < int(end.timestamp()*1000)

def extract(raw, received_ms=None):
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    subject, sender = str(mail.get('Subject','')), str(mail.get('From',''))
    plain, html = [], []
    for part in mail.walk():
        if part.get_content_disposition() == 'attachment':
            continue
        if part.get_content_type() in ('text/plain','text/html'):
            value = part.get_content()
            (plain if part.get_content_type() == 'text/plain' else html).append(value)
    soup = BeautifulSoup('\n'.join(html), 'html.parser')
    for tag in soup(['script','style']): tag.decompose()
    for tag in soup.find_all(['p','div','br','li','tr','h1','h2','h3']):
        tag.insert_before('\n'); tag.insert_after('\n')
    body = '\n'.join(plain) if plain else soup.get_text()
    if not KEY.search(subject+'\n'+body): return None
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
    excerpts = [p for p in paragraphs if KEY.search(p) or INSTRUCTION.search(p)]
    links = []
    def add(label, url):
        if url.startswith(('http://','https://')) and not FOOTER.search(label+' '+url) and (label,url) not in links:
            links.append((label,url))
    for p in paragraphs:
        if KEY.search(p) or INSTRUCTION.search(p):
            for match in URL.finditer(p): add('Link in original text', match.group())
    for a in soup.find_all('a', href=True):
        label = a.get_text(' ', strip=True)
        context = a.parent.get_text(' ',strip=True) if a.parent else label
        if INSTRUCTION.search(label+' '+context) or KEY.search(context): add(label or 'Unlabelled link', a['href'])
    # A sole non-footer button/link is a plausible participation target.
    candidates = [(a.get_text(' ',strip=True) or 'Unlabelled link', a['href']) for a in soup.find_all('a', href=True) if a['href'].startswith(('https://','http://')) and not FOOTER.search(a.get_text(' ',strip=True)+' '+a['href'])]
    if not links and len(candidates)==1: add(*candidates[0])
    text = f'Subject: {subject}\nFrom: {sender}\n\n'+'\n\n'.join(excerpts)
    text += '\n\nParticipation links:\n'+'\n\n'.join(f'{label}\n{url}' for label,url in links) if links else f"\n\nCannot extract the participation link. Please check Gmail: '{subject}'."
    try:
        sent = parsedate_to_datetime(str(mail.get('Date', '')))
        if sent.tzinfo is None:
            raise ValueError('Missing timezone')
        stamp_label = 'Sent'
    except (ValueError, TypeError, OverflowError):
        sent = datetime.fromtimestamp(int(received_ms)/1000, TZ) if received_ms is not None else None
        stamp_label = 'Received (sent date unavailable)'
    if sent is not None:
        sent = sent.astimezone(TZ)
        weekdays = ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')
        months = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
        stamp = f'{weekdays[sent.weekday()]}, {months[sent.month-1]} {sent.day}, {sent.hour % 12 or 12}:{sent.minute:02d} {"AM" if sent.hour < 12 else "PM"}'
        text += f'\n\n{stamp_label}: {stamp} (Malaysia time)'
    else:
        text += '\n\nSent: date unavailable'
    return text

def split_text(text, limit=3900):
    # Count UTF-16 code units conservatively. Never drop characters, including URLs.
    parts, chunk, size = [], [], 0
    for char in text:
        units = len(char.encode('utf-16-le'))//2
        if size+units > limit:
            joined=''.join(chunk)
            cut=max(joined.rfind(' '),joined.rfind('\n'))+1
            if cut>len(joined)//2:
                parts.append(joined[:cut]); chunk=list(joined[cut:]); size=len(joined[cut:].encode('utf-16-le'))//2
            else:
                parts.append(joined); chunk=[]; size=0
        chunk.append(char); size+=units
    if chunk: parts.append(''.join(chunk))
    return parts


def split_alert(text):
    """Repeat the email timestamp at the bottom of each Telegram part."""
    content, separator, footer = text.rpartition('\n\n')
    if separator and (footer.startswith('Sent:') or footer.startswith('Received:') or footer.startswith('Received (sent date unavailable):')):
        suffix = separator + footer
        return [part + suffix for part in split_text(content, 3900-len(suffix.encode('utf-16-le'))//2)]
    return split_text(text)
