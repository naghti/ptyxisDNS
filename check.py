#!/usr/bin/env python3
"""Anonymous routing diagnostics: never reads or sends account tokens."""
import concurrent.futures
import html
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile

CANDIDATES = ('45.13.237.213', '37.221.93.128', '37.221.93.141', '5.175.161.40', '5.175.161.3', '31.25.239.132', '143.20.64.192')
INTERFACE = None


def probe(label, ip=None, path='/', direct=True):
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / 'body'
        headers = Path(directory) / 'headers'
        args = ['curl', '-q', '--silent', '--show-error', '--connect-timeout', '5',
                '--max-time', '12', '--max-filesize', '2000000', '--output', str(body),
                '--dump-header', str(headers), '--write-out', '%{http_code} %{remote_ip}']
        if INTERFACE:
            args += ['--interface', 'if!' + INTERFACE]
        if path == '/backend-api/codex/responses':
            args += ['-H', 'Content-Type: application/json', '--data', '{}']
        if direct:
            args += ['--noproxy', '*']
        if ip:
            args += ['--resolve', 'chatgpt.com:443:' + ip]
        result = subprocess.run(args + ['https://chatgpt.com' + path], capture_output=True, text=True)
        content = body.read_text(errors='replace') if body.exists() else ''
        hdr = headers.read_text(errors='replace') if headers.exists() else ''
        # Strip style/script so a block page's actual explanation is visible.
        clean = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', content, flags=re.S | re.I)
        clean = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', clean))).strip()
        lines = [f'{label}: HTTP/IP={result.stdout.strip()} curl_exit={result.returncode}']
        for line in hdr.splitlines():
            if line.lower().startswith(('server:', 'cf-ray:', 'cf-mitigated:', 'location:')):
                lines.append('  ' + line)
        if result.stderr:
            lines.append('  ' + result.stderr.strip())
        lines.append('  Ответ: ' + clean[:600])
        status = result.stdout.split()[0] if result.stdout.split() else '000'
        page_ok = status == '200' and 'chatgpt' in content.lower()
        api_reachable = False
        if path == '/backend-api/codex/responses' and status == '401':
            try:
                api_reachable = json.loads(content).get('detail') == 'Unauthorized'
            except (ValueError, AttributeError):
                pass
        if api_reachable:
            lines.append('  Endpoint доступен: штатный JSON 401 на запрос без токена; это не проверка авторизации.')
        return '\n'.join(lines), result.returncode == 0 and (page_ok or api_reachable)


def main():
    global INTERFACE
    if '--interface' in sys.argv:
        INTERFACE = sys.argv[sys.argv.index('--interface') + 1]
        socket.if_nametoindex(INTERFACE)
    print('Выход:', ('только интерфейс ' + INTERFACE) if INTERFACE else 'системные маршруты (могут включать VPN)')
    print('Транспорт команд:', os.environ.get('TERMINAL_DNS_TRANSPORT', 'hosts only'))
    print('Окружение:', os.environ.get('TERMINAL_DNS_ACTIVE', 'НЕ АКТИВНО'))
    try:
        print('Системный resolver внутри окна:', ', '.join(sorted({a[4][0] for a in socket.getaddrinfo('chatgpt.com', 443)})))
    except OSError as error:
        print('Ошибка resolver:', error)
    proxies = [key for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy') if os.environ.get(key)]
    print('Заданные proxy-переменные (значения скрыты):', ', '.join(proxies) or 'нет')
    jobs = [('Главная страница ChatGPT', None, '/', True),
            ('Codex endpoint, БЕЗ авторизации', None, '/backend-api/codex/responses', True)]
    if '--diagnose' in sys.argv:
        if proxies and not INTERFACE:
            jobs.append(('С унаследованными proxy', None, '/', False))
        jobs += [(f'GeoHide EU {ip}', ip, '/backend-api/codex/responses', True) for ip in CANDIDATES]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda job: probe(*job), jobs))
    for report, _ in results:
        print('\n' + report)
    print('\nHTTP 200 главной страницы не подтверждает работу Codex. Проверка endpoint без токена не проверяет авторизацию. 403 не считается успехом.')
    print('Анонимный endpoint: отвечает. Работа Codex НЕ проверена; выполни runDNS --test-codex.' if results[1][1] else 'Анонимный endpoint: доступ НЕ подтверждён')
    return 0 if results[1][1] else 1


if __name__ == '__main__':
    sys.exit(main())
