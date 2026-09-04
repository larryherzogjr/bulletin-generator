"""Exercise deployment control flow without touching Git, sudo, or systemd."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('preflight_fails', [False, True])
def test_updater_loads_service_environment_and_waits_for_startup(tmp_path, preflight_fails):
    checkout = tmp_path / 'checkout'
    commands = tmp_path / 'bin'
    checkout.mkdir()
    commands.mkdir()
    (checkout / '.venv/bin').mkdir(parents=True)
    log = tmp_path / 'commands.jsonl'
    counter = tmp_path / 'health-count'
    stub = commands / 'stub'
    stub.write_text(f'''#!{sys.executable}
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['DEPLOY_TEST_LOG'], 'a') as log:
    log.write(json.dumps([name] + args) + '\\n')
if name == 'git' and args[:1] == ['rev-parse']:
    print('previous-revision')
if name == 'sudo' and args[:1] == ['systemd-run']:
    sys.exit(int(os.environ['DEPLOY_TEST_PREFLIGHT_FAILS']))
if name == 'curl':
    counter = pathlib.Path(os.environ['DEPLOY_TEST_COUNTER'])
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    sys.exit(0 if count >= 2 else 7)
''')
    stub.chmod(0o755)
    for name in ['git', 'sudo', 'npm', 'curl', 'sleep']:
        (commands / name).symlink_to(stub)
    (checkout / '.venv/bin/python').symlink_to(stub)
    script = Path(__file__).resolve().parents[1] / 'deploy/update.sh'
    env = dict(os.environ, PATH=f'{commands}{os.pathsep}{os.environ["PATH"]}',
               APP_DIR=str(checkout), ENV_FILE='/etc/test-bulletin.env',
               BULLETIN_DB='/var/lib/bulletin/test.sqlite3',
               SERVICE_USER='bulletin', SERVICE_GROUP='bulletin',
               DEPLOY_TEST_LOG=str(log), DEPLOY_TEST_COUNTER=str(counter),
               DEPLOY_TEST_PREFLIGHT_FAILS=str(int(preflight_fails)))
    result = subprocess.run(['bash', str(script)], env=env, text=True,
                            capture_output=True, timeout=10)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    preflight = next(call for call in calls if call[:2] == ['sudo', 'systemd-run'])
    assert '--property=EnvironmentFile=-/etc/test-bulletin.env' in preflight
    assert '--property=User=bulletin' in preflight
    assert '--property=Group=bulletin' in preflight
    assert '--setenv=BULLETIN_DB=/var/lib/bulletin/test.sqlite3' in preflight
    assert {'--wait', '--pipe', '--collect'} <= set(preflight)
    assert preflight[-2:] == ['check', '--render']
    assert counter.read_text() == '3'
    assert all('--max-time' in call for call in calls if call[0] == 'curl')
    if preflight_fails:
        assert result.returncode == 1
        assert ['git', 'reset', '--hard', 'previous-revision'] in calls
        assert 'rollback healthy' in result.stderr
        assert 'rollback health check also failed' not in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert '==> done' in result.stdout
        assert not any(call[:2] == ['git', 'reset'] for call in calls)
