import os, sqlite3, secrets, hmac, json, sys, urllib.request
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from contextlib import contextmanager
from flask import Flask, request, render_template, abort, redirect, url_for, jsonify

app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=16384
TZ=ZoneInfo('Asia/Tehran')
DB=os.getenv('SALON_DB','salon.sqlite3')
@contextmanager
def db(write=False):
    c=sqlite3.connect(DB,timeout=10)
    try:
        with c:
            c.row_factory=sqlite3.Row
            if write: c.execute('BEGIN IMMEDIATE')
            yield c
    finally: c.close()
with db() as c:
    c.executescript('''CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY,name TEXT NOT NULL,price INTEGER NOT NULL,duration INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY,service INTEGER,name TEXT,phone TEXT,start INTEGER,end INTEGER,token TEXT,cancelled INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS sent(booking INTEGER,start INTEGER,channel TEXT,PRIMARY KEY(booking,start,channel));
    CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY, opening TEXT, closing TEXT, reminder INTEGER);''')
    c.execute('INSERT OR IGNORE INTO settings VALUES(1,\'09:00\',\'19:00\',120)')
    c.executemany('INSERT OR IGNORE INTO services VALUES(?,?,?,?)',[(1,'اصلاح مو',180000,30),(2,'اصلاح ریش',90000,20),(3,'رنگ مو',500000,90)])

def settings(c): return c.execute('SELECT * FROM settings').fetchone()
def stamp(day,clock): return int(datetime.combine(day,time.fromisoformat(clock),TZ).timestamp())
def slots(c,day,duration,skip=0):
    cfg=settings(c); start=stamp(day,cfg['opening']); end=stamp(day,cfg['closing'])
    used=c.execute('SELECT start,end FROM bookings WHERE cancelled=0 AND id!=? AND start<? AND end>?',(skip,end,start)).fetchall()
    now=datetime.now(TZ).timestamp(); length=duration*60
    return [i for i in range(start,end-length+1,900) if i>now and not any(i<r['end'] and i+length>r['start'] for r in used)]
def iso(ts): return datetime.fromtimestamp(ts,TZ).isoformat()
@app.get('/')
def home():
    with db() as c: return render_template('index.html',services=c.execute('SELECT * FROM services').fetchall(),today=datetime.now(TZ).date())
@app.get('/slots')
def available():
    try: day=date.fromisoformat(request.args['day']); s=int(request.args['service'])
    except (ValueError,KeyError): abort(400)
    today=datetime.now(TZ).date()
    if not today<=day<=today+timedelta(days=90): return jsonify([])
    with db() as c:
        r=c.execute('SELECT duration FROM services WHERE id=?',(s,)).fetchone()
        if not r: abort(404)
        return jsonify([{'id':i,'time':iso(i)[11:16]} for i in slots(c,day,r[0])])
@app.post('/book')
def book():
    f=request.form; name=f.get('name','').strip(); phone=f.get('phone','').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')).strip()
    if not name or len(name)>80 or len(phone)!=11 or not phone.isascii() or not phone.isdigit() or not phone.startswith('09'): return 'نام یا شمارهٔ موبایل معتبر نیست.',400
    try: start=int(f['start']); day=datetime.fromtimestamp(start,TZ).date(); s=int(f['service'])
    except (ValueError,KeyError,OverflowError,OSError): abort(400)
    today=datetime.now(TZ).date()
    with db(True) as c:
        r=c.execute('SELECT duration FROM services WHERE id=?',(s,)).fetchone()
        if not r or not today<=day<=today+timedelta(days=90) or start not in slots(c,day,r[0]): return 'این ساعت دیگر آزاد نیست؛ دوباره انتخاب کنید.',409
        c.execute('INSERT INTO bookings(service,name,phone,start,end,token) VALUES(?,?,?,?,?,?)',(s,name,phone,start,start+r[0]*60,f.get('token','')[:4096]))
    return jsonify(message='نوبت شما ثبت شد.')
@app.route('/admin',methods=['GET','POST'])
def admin():
    pw=os.getenv('SALON_ADMIN_PASSWORD',''); auth=request.authorization
    if not pw or not auth or auth.type!='basic' or not hmac.compare_digest((auth.password or '').encode(),pw.encode()):
        return 'ورود مدیر',401,{'WWW-Authenticate':'Basic realm="Ebrahim Salon"'}
    csrf=hmac.digest(pw.encode(),b'salon-admin-action','sha256').hex()
    if request.method=='POST':
        f=request.form
        if not hmac.compare_digest(f.get('csrf',''),csrf): abort(403)
        try:
            with db(True) as c:
                action=f['action']
                if action=='cancel': c.execute('UPDATE bookings SET cancelled=1 WHERE id=?',(int(f['id']),))
                elif action=='move':
                    i=int(f['id']); day=date.fromisoformat(f['day']); start=stamp(day,f['clock']); r=c.execute('SELECT * FROM bookings WHERE id=? AND cancelled=0',(i,)).fetchone()
                    if not r or start not in slots(c,day,(r['end']-r['start'])//60,i): return 'زمان جدید آزاد نیست.',409
                    c.execute('UPDATE bookings SET start=?,end=? WHERE id=?',(start,start+r['end']-r['start'],i))
                elif action=='service':
                    name=f['name'].strip(); price=int(f['price']); duration=int(f['duration']); i=int(f['id'])
                    if not 1<=len(name)<=80 or not 0<=price<=10**10 or not 5<=duration<=480: abort(400)
                    if i: c.execute('UPDATE services SET name=?,price=?,duration=? WHERE id=?',(name,price,duration,i))
                    else: c.execute('INSERT INTO services(name,price,duration) VALUES(?,?,?)',(name,price,duration))
                elif action=='settings':
                    a=time.fromisoformat(f['opening']); b=time.fromisoformat(f['closing']); m=int(f['reminder'])
                    if a>=b or not 0<=m<=1440: abort(400)
                    c.execute('UPDATE settings SET opening=?,closing=?,reminder=?',(a.isoformat(),b.isoformat(),m))
                else: abort(400)
        except (ValueError,KeyError,OverflowError): abort(400)
        return redirect(url_for('admin'),303)
    with db() as c:
        return render_template('admin.html',csrf=csrf,cfg=settings(c),services=c.execute('SELECT * FROM services').fetchall(),rows=c.execute('SELECT b.*,s.name AS service_name FROM bookings b JOIN services s ON s.id=b.service ORDER BY start DESC').fetchall(),iso=iso)

def remind():
    sms=os.getenv('SALON_SMS_WEBHOOK'); secret=os.getenv('SALON_SMS_SECRET',''); push=os.getenv('SALON_FIREBASE')=='1'
    if push:
        import firebase_admin
        from firebase_admin import messaging
        firebase_admin.initialize_app()
    now=int(datetime.now(TZ).timestamp())
    with db() as c:
        rows=c.execute('SELECT * FROM bookings WHERE cancelled=0 AND start>? AND start<=?',(now,now+settings(c)['reminder']*60)).fetchall()
    for r in rows:
        for channel in ['sms','push']:
            if channel=='sms' and not sms or channel=='push' and (not push or not r['token']): continue
            try:
                with db(True) as c:
                    if not c.execute('SELECT 1 FROM bookings WHERE id=? AND start=? AND cancelled=0',(r['id'],r['start'])).fetchone(): continue
                    k=(r['id'],r['start'],channel)
                    if c.execute('SELECT 1 FROM sent WHERE booking=? AND start=? AND channel=?',k).fetchone(): continue
                    text='یادآوری نوبت آرایشگاه ابراهیم، ساعت '+iso(r['start'])[11:16]
                    if channel=='sms':
                        req=urllib.request.Request(sms,json.dumps({'phone':r['phone'],'message':text}).encode(),{'Content-Type':'application/json','Authorization':'Bearer '+secret,'Idempotency-Key':f"{r['id']}-{r['start']}"},method='POST')
                        with urllib.request.urlopen(req,timeout=5): pass
                    else: messaging.send(messaging.Message(notification=messaging.Notification(title='آرایشگاه ابراهیم',body=text),android=messaging.AndroidConfig(notification=messaging.AndroidNotification(channel_id='salon_reminders')),token=r['token']))
                    c.execute('INSERT INTO sent VALUES(?,?,?)',k)
            except Exception as e: print('Reminder failed:',channel,type(e).__name__,file=sys.stderr)

if __name__=='__main__':
    if sys.argv[1:]==['remind']: remind()
    else: app.run()
