import subprocess
import sys
from pathlib import Path

HELPER=Path(__file__).resolve().parent.parent/'cloud/copy-secret.py'

def test_secret_helper_windows_safe_file_arguments(tmp_path):
    env=tmp_path/'space folder'; env.mkdir()
    path=env/'.env'; path.write_text('TELEGRAM_BOT_TOKEN="dummy:test-value"\nTELEGRAM_CHAT_ID=123456\n')
    result=subprocess.run([sys.executable,str(HELPER),str(path),'TELEGRAM_BOT_TOKEN'],capture_output=True,text=True)
    assert result.returncode==0
    assert result.stdout=='dummy:test-value'
    assert not result.stderr

def test_secret_helper_missing_setting(tmp_path):
    path=tmp_path/'.env'; path.write_text('TELEGRAM_BOT_TOKEN=replace_locally\n')
    result=subprocess.run([sys.executable,str(HELPER),str(path),'TELEGRAM_BOT_TOKEN'],capture_output=True,text=True)
    assert result.returncode==1
    assert result.stdout==''
