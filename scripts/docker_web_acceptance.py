"""Real Compose/browser acceptance. No mock models; isolated persistent mounts.

Requires an already built vision-stage3:local image, Docker CLI, Edge, Playwright.
Credentials are generated in memory; only salted password hash is stored.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker', default='docker')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--ubuntu', help='Use this WSL distribution to run Compose')
    parser.add_argument('--images', default='D001,D002,D003,D004,D005,D006')
    args = parser.parse_args()
    output = ROOT / 'results' / ('docker-web-' + time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True)
    for directory in ['data', 'models', 'video']:
        (output / directory).mkdir()
    password = secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    encoded = 'pbkdf2_sha256$310000$' + salt.hex() + '$' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310000).hex()
    envfile = output / '.env'
    envfile.write_text(
        "DEMO_USER=container-test\nDEMO_PASSWORD_HASH='" + encoded + "'\nJWT_SECRET=" + secrets.token_urlsafe(48)
        + '\nVLM_MODEL=qwen3-vl:4b\nVLM_NUM_PREDICT=4000\nVLM_TIMEOUT_SECONDS=120\n'
        + 'APP_ENV_FILE=' + envfile.as_posix() + '\nAPP_DATA_DIR=' + (output / 'data').as_posix()
        + '\nAPP_RESULTS_DIR=' + (output / 'models').as_posix() + '\nAPP_PORT=' + str(args.port) + '\n', encoding='utf-8')
    compose = [args.docker, 'compose', '--project-name', 'vision-stage3-acceptance', '--env-file', str(envfile)]
    if args.ubuntu:
        def linux_path(path):
            return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]
        compose = [r'C:\Windows\System32\wsl.exe', '-d', args.ubuntu, '--cd', linux_path(ROOT), '--', 'env',
                   'APP_ENV_FILE=' + linux_path(envfile), 'APP_DATA_DIR=' + linux_path(output / 'data'),
                   'APP_RESULTS_DIR=' + linux_path(output / 'models'), 'APP_PORT=' + str(args.port),
                   'docker', 'compose', '--project-name', 'vision-stage3-acceptance', '--env-file', linux_path(envfile)]
    summary = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff'], cwd=ROOT)).hexdigest(),
               'deployment': ('WSL2 ' + args.ubuntu + ' + Docker Desktop') if args.ubuntu else 'Docker Desktop Linux containers',
               'yolo_weights_sha256': hashlib.sha256((ROOT / 'yolo11n.pt').read_bytes()).hexdigest(),
               'url': f'http://127.0.0.1:{args.port}', 'tasks': [], 'restart_verified': False}

    def command(label, command_args, timeout=180):
        result = subprocess.run(command_args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        (output / (label + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'{label} failed ({result.returncode}); see {output / (label + ".log")}')
        return result.stdout

    def ready():
        for _ in range(120):
            try:
                response = requests.get(summary['url'] + '/health', timeout=3)
                if response.ok:
                    assert response.json()['task_mode'] == 'celery'
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        raise RuntimeError('Nginx/API health check timed out')

    try:
        command('compose-validation', compose + ['config', '-q'])
        command('startup', compose + ['up', '-d', '--no-build', '--wait'], timeout=300)
        ready()
        command('containers', compose + ['ps'])
        command('image', [args.docker, 'image', 'inspect', 'vision-stage3:local', '--format', '{{.Id}}'])
        command('ollama', compose + ['exec', '-T', 'worker', 'python', '-c',
            "import os,requests; r=requests.get(os.environ['OLLAMA_BASE_URL']+'/api/tags',timeout=15); r.raise_for_status(); print([m['name'] for m in r.json()['models']]); assert any(m['name']=='qwen3-vl:4b' for m in r.json()['models'])"])
        command('dependencies', compose + ['exec', '-T', 'worker', 'pip', 'freeze'])
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1080}, record_video_dir=str(output / 'video'))
            page = context.new_page()
            page.goto(summary['url'])
            page.fill('#username', 'container-test')
            page.fill('#password', password)
            page.click('#loginForm button')
            page.wait_for_selector('#workspace', state='visible')
            for item in csv.DictReader((ROOT / 'data/manifest.csv').open(encoding='utf-8-sig')):
                if item['image_id'] not in args.images.split(','):
                    continue
                path = ROOT / item['path']
                page.set_input_files('#file', str(path))
                page.click('#run')
                page.wait_for_function("document.querySelector('#status').textContent.includes('SHA-256')", timeout=30000)
                page.wait_for_function("!document.querySelector('#run').disabled", timeout=900000)
                tid = page.evaluate("localStorage.getItem('taskId')")
                task = page.evaluate("async id=>{const r=await fetch('/api/tasks/'+id,{headers:{Authorization:'Bearer '+sessionStorage.getItem('token')}});if(!r.ok)throw Error(r.status);return r.json()}", tid)
                assert task['image_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
                assert task['status'] in ['success', 'partial_success', 'failed']
                if task['yolo_status'] == 'success':
                    page.wait_for_function("document.querySelector('#detected').naturalWidth>0 && !document.querySelector('#detected').hidden")
                task['source_image_id'] = item['image_id']
                summary['tasks'].append(task)
                page.locator('#status').scroll_into_view_if_needed()
                page.wait_for_timeout(2000)  # Record actual model panels in the video.
                page.locator('#countsTable').scroll_into_view_if_needed()
                page.wait_for_timeout(2000)
                page.screenshot(path=str(output / (item['image_id'] + '.png')), full_page=True)
                print(item['image_id'], task['status'], task['error'], flush=True)
                page.reload()
                page.wait_for_function("document.querySelector('#status').textContent.includes('SHA-256')", timeout=30000)
            # Same browser and persisted token restore results after all services restart.
            command('restart', compose + ['restart'], timeout=180)
            ready()
            page.reload()
            page.wait_for_function("document.querySelector('#status').textContent.includes('SHA-256')", timeout=30000)
            for task in summary['tasks']:
                restored = page.evaluate("async id=>(await fetch('/api/tasks/'+id,{headers:{Authorization:'Bearer '+sessionStorage.getItem('token')}})).json()", task['task_id'])
                assert all(restored[key] == task[key] for key in ['status', 'image_sha256', 'yolo', 'vlm', 'comparison'])
                status = page.evaluate("async id=>(await fetch('/api/tasks/'+id+'/image/original',{headers:{Authorization:'Bearer '+sessionStorage.getItem('token')}})).status", task['task_id'])
                assert status == 200
            summary['restart_verified'] = True
            page.screenshot(path=str(output / 'after-restart.png'), full_page=True)
            assert requests.get(summary['url'] + '/api/history', timeout=5).status_code == 401
            summary['unauthorized_rejected'] = True
            context.close()
            browser.close()
        command('sqlite', compose + ['exec', '-T', 'api', 'python', '-c', "import sqlite3; c=sqlite3.connect('/app/data/stage3.db'); print(c.execute('select id,status,yolo_status,vlm_status,image_sha256 from tasks').fetchall())"])
    except Exception as exc:
        summary['acceptance_error'] = str(exc)
        raise
    finally:
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        try:
            command('services', compose + ['logs', '--no-color', '--tail', '500'])
        except Exception:
            pass
        print('EVIDENCE', output, flush=True)


if __name__ == '__main__':
    main()
