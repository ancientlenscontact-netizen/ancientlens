from types import SimpleNamespace
import pytest
from app.data import monitored_backup as monitor

@pytest.mark.parametrize('code,state',[(0,'success'),(1,'failure')])
def test_only_status_sent_after_backup(monkeypatch,code,state):
    url='https://hc-ping.com/11111111-1111-1111-1111-111111111111'
    monkeypatch.setenv('ANCIENTLENS_BACKUP_PING_URL',url)
    calls=[]
    monkeypatch.setattr(monitor,'ping',lambda u,s:calls.append(s))
    def execute(args):
        assert args[1:3]==['-m','app.data.offdevice']
        assert url not in args
        calls.append('backup')
        return SimpleNamespace(returncode=code)
    monkeypatch.setattr(monitor.subprocess,'run',execute)
    assert monitor.run(['--production'])==code
    assert calls==['start','backup',state]

def test_invalid_or_missing_url_never_runs_backup(monkeypatch,capsys):
    monkeypatch.setenv('ANCIENTLENS_BACKUP_PING_URL','https://unexpected.example/private-token')
    monkeypatch.setattr(monitor.subprocess,'run',lambda _:pytest.fail('must not run'))
    assert monitor.run([])==1
    assert 'private-token' not in capsys.readouterr().err

def test_notification_failure_does_not_fake_success(monkeypatch,capsys):
    monkeypatch.setenv('ANCIENTLENS_BACKUP_PING_URL','https://hc-ping.com/11111111-1111-1111-1111-111111111111')
    monkeypatch.setattr(monitor,'ping',lambda *args:(_ for _ in ()).throw(RuntimeError('secret-url')))
    monkeypatch.setattr(monitor.subprocess,'run',lambda _:SimpleNamespace(returncode=0))
    assert monitor.run([])==1
    assert 'secret-url' not in capsys.readouterr().err
