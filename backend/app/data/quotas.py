import time

class QuotaExceeded(Exception):
    pass

def consume(db, account_id, kind, limit):
    """Call inside the same write transaction: failures do not consume successful-write quota."""
    if not db.execute('SELECT 1 FROM accounts WHERE id=? AND closed_on IS NULL',(account_id,)).fetchone():
        raise PermissionError('Account is closed')
    window=int(time.time())//3600
    db.execute('DELETE FROM write_quotas WHERE window<?',(window-24,))
    count=db.execute('SELECT used FROM write_quotas WHERE account_id=? AND kind=? AND window=?',(account_id,kind,window)).fetchone()
    if count and count[0]>=limit:
        raise QuotaExceeded(f'Hourly {kind} limit reached. Try again in the next hour.')
    db.execute('INSERT INTO write_quotas VALUES (?,?,?,1) ON CONFLICT(account_id,kind,window) DO UPDATE SET used=used+1',(account_id,kind,window))
