"""Real browser + HTTP + model regression. Never mocks model calls."""
import argparse
import csv
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--budget', default='500')
    parser.add_argument('--images', default='D001,D002,D003,D004,D005,D006')
    args = parser.parse_args()
    output = ROOT / 'results' / 'acceptance' / (time.strftime('%Y%m%d-%H%M%S') + '-' + args.budget)
    output.mkdir(parents=True)
    env = dict(os.environ)
    # Generate only ephemeral credentials, never print or save their plaintext.
    password = secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    import hashlib
    env.update(JWT_SECRET=secrets.token_urlsafe(48), DEMO_USER='browser-test',
               DEMO_PASSWORD_HASH='pbkdf2_sha256$310000$'+salt.hex()+'$'+hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310000).hex(),
               TASK_MODE='local', DATABASE_URL='sqlite:///'+str(output / 'tasks.db'),
               UPLOAD_DIR=str(output / 'uploads'), RESULT_DIR=str(output / 'models'),
               VLM_NUM_PREDICT=args.budget, YOLO_AUTOINSTALL='false')
    log = (output / 'server.log').open('w', encoding='utf-8')
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'src.web_app:app', '--host', '127.0.0.1', '--port', '8765'], cwd=ROOT, env=env, stdout=log, stderr=log)
    rows = []
    try:
        import requests
        for _ in range(60):
            try:
                if requests.get('http://127.0.0.1:8765/health', timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.5)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True)
            context = browser.new_context(viewport={'width':1280,'height':1000}, record_video_dir=str(output / 'video'))
            page = context.new_page()
            page.goto('http://127.0.0.1:8765')
            page.fill('#username', 'browser-test')
            page.fill('#password', password)
            page.click('#loginForm button')
            page.wait_for_selector('#workspace', state='visible')
            for item in csv.DictReader((ROOT / 'data/manifest.csv').open(encoding='utf-8-sig')):
                if item['image_id'] not in args.images.split(','):
                    continue
                page.set_input_files('#file', str(ROOT / item['path']))
                page.click('#run')
                page.wait_for_function("document.querySelector('#status').textContent.includes('SHA-256')", timeout=30000)
                page.wait_for_function("!document.querySelector('#run').disabled", timeout=600000)
                tid = page.evaluate("localStorage.getItem('taskId')")
                body = page.evaluate("async id => {const r=await fetch('/api/tasks/'+id,{headers:{Authorization:'Bearer '+sessionStorage.getItem('token')}});return r.json()}",tid)
                body['source_image_id'] = item['image_id']
                rows.append(body)
                page.screenshot(path=str(output / (item['image_id']+'.png')), full_page=True)
                print(item['image_id'], body['status'], body['yolo_status'], body['vlm_status'], body['error'], flush=True)
                # Check page refresh actually restores the saved task.
                page.reload()
                page.wait_for_function("document.querySelector('#status').textContent.includes('SHA-256')",timeout=30000)
            page.fill('#note', '真实浏览器验收备注')
            page.click('#saveNote')
            page.wait_for_function("document.querySelector('#message').textContent.includes('备注已保存')")
            page.click('#clear')
            assert page.locator('#preview').is_hidden()
            page.click('#logout')
            assert page.locator('#login').is_visible()
            page.screenshot(path=str(output / 'logout.png'), full_page=True)
            context.close()
            browser.close()
        metadata = {'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'worktree_diff_sha256': hashlib.sha256(subprocess.check_output(['git','diff'],cwd=ROOT)).hexdigest(), 'task_mode':'local', 'redis_verified':False,'budget':args.budget,'tasks':rows}
        (output / 'summary.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        print('EVIDENCE',output,flush=True)
    finally:
        server.terminate()
        server.wait(timeout=30)
        log.close()


if __name__ == '__main__':
    main()
