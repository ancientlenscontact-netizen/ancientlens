"""Local, hidden-input setup. Does not print secrets or contact Backblaze."""
import getpass
import json
import os
from pathlib import Path
import sys

REPOSITORY='s3:https://s3.example.invalid/your-private-bucket/restic'


def save_private(destination, key_id, application_key, password):
    destination=Path(destination)
    if destination.is_symlink() or any(p.is_symlink() for p in destination.parents):
        raise ValueError('Credential path must not contain symlinks')
    if not key_id or not application_key or len(password)<20:
        raise ValueError('Keys required; encryption password must be at least 20 characters')
    destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(destination.parent,0o700)
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:
        json.dump({'repository':REPOSITORY,'key_id':key_id,'application_key':application_key,'password':password},output)
        output.flush();os.fsync(output.fileno())


def main():
    if not sys.stdin.isatty(): raise SystemExit('Use an interactive terminal; redirected input is not accepted.')
    destination=Path(__file__).resolve().parents[3]/'.local/offdevice/credentials.json'
    if destination.exists(): raise SystemExit('Configuration exists; refusing to overwrite.')
    print('AncientLens private backup setup. Input is hidden. No upload occurs.')
    key_id=getpass.getpass('Backblaze keyID: ').strip()
    key=getpass.getpass('Backblaze applicationKey: ').strip()
    password=getpass.getpass('Backup-encryption password (20+ characters): ')
    if password!=getpass.getpass('Repeat backup-encryption password: '):
        raise SystemExit('Passwords differ; nothing saved.')
    if input('Saved encryption password independently in your password manager? Type yes: ').strip().lower()!='yes':
        raise SystemExit('Nothing saved. Save the password independently before retrying.')
    save_private(destination,key_id,key,password)
    print('Private configuration saved. No upload performed.')


if __name__=='__main__':
    try: main()
    except (ValueError,FileExistsError): raise SystemExit('Configuration rejected or already exists; nothing overwritten.')
