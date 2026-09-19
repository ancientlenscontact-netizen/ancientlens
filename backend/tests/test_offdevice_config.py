import json
import pytest
from app.data.configure_offdevice import save_private,REPOSITORY

def test_private_config_refuses_overwrite(tmp_path):
    target=tmp_path/'private/config.json'
    save_private(target,'fixture-id','fixture-key','software fixture password only')
    assert target.stat().st_mode & 0o777 == 0o600
    assert target.parent.stat().st_mode & 0o777 == 0o700
    assert json.loads(target.read_text())['repository']==REPOSITORY
    with pytest.raises(FileExistsError): save_private(target,'other','other','other fixture password only')
    assert json.loads(target.read_text())['key_id']=='fixture-id'

def test_rejects_symlinks_and_invalid_values(tmp_path):
    target=tmp_path/'actual';target.mkdir();alias=tmp_path/'alias';alias.symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError): save_private(alias/'config.json','id','key','software fixture password only')
    with pytest.raises(ValueError): save_private(target/'config.json','id','','short')
    assert not (target/'config.json').exists()
