#!/usr/bin/env python3
"""Real authenticated request via the same transport as the interactive shell."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix='terminal-dns-model-') as directory:
    output = Path(directory) / 'reply'
    print('Проверка настоящего ответа Codex; используется текущий аккаунт.', flush=True)
    print('Транспорт:', os.environ.get('TERMINAL_DNS_TRANSPORT', 'unknown'),
          'Интерфейс:', os.environ.get('TERMINAL_DNS_INTERFACE') or 'системный маршрут', flush=True)
    try:
        result = subprocess.run(['codex', 'exec', '--ephemeral', '--skip-git-repo-check',
                                 '--sandbox', 'read-only', '-C', directory, '-o', str(output),
                                 'Connectivity test. Do not run tools or inspect files. Reply exactly PTYXIS_DNS_MODEL_OK.'],
                                stdin=subprocess.DEVNULL, timeout=120)
        ok = result.returncode == 0 and output.exists() and output.read_text().strip() == 'PTYXIS_DNS_MODEL_OK'
    except subprocess.TimeoutExpired:
        ok = False
        print('Запрос модели не завершился за 120 секунд.')
    print('Ответ модели через codex exec: ' + ('ПОДТВЕРЖДЁН' if ok else 'НЕ подтверждён'))
    print('Этот тест проверяет codex exec. Для обычного codex в DNS-окне автоматически добавляется --no-daemon.')
    sys.exit(0 if ok else 1)
