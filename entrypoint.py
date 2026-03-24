#!/bin/python3
import json
import os
import sys
import requests
from github import Github

os.system("git config --global --add safe.directory '*'")

model    = os.getenv('INPUT_MODEL')    or (sys.argv[1] if len(sys.argv) > 1 else None)
language = os.getenv('INPUT_LANGUAGE') or (sys.argv[2] if len(sys.argv) > 2 else None)
url_base = os.getenv('INPUT_URL')      or (sys.argv[3] if len(sys.argv) > 3 else None)

if not model or not language or not url_base:
    print("❌ Errore: model, language e url sono obbligatori.")
    sys.exit(1)

SUPPORTED_LANGUAGES = ['terraform', 'kubernetes']
if language not in SUPPORTED_LANGUAGES:
    print(f"⚠️ Linguaggio '{language}' non supportato. Scegli tra: {', '.join(SUPPORTED_LANGUAGES)}")
    sys.exit(1)

github_token = os.getenv('GITHUB_TOKEN')
github_repo  = os.getenv('GITHUB_REPOSITORY')
github_sha   = os.getenv('GITHUB_SHA')

if not github_token or not github_repo or not github_sha:
    print("❌ Variabili d'ambiente GitHub mancanti.")
    sys.exit(1)

g     = Github(github_token)
repo  = g.get_repo(github_repo)
files = repo.get_commit(sha=github_sha).files

print(f"\n🔍 Analisi commit {github_sha} su repo {github_repo}")
print(f"📦 Modello: {model} | 🌐 Backend: {url_base} | 🗂 Linguaggio: {language}\n")


def extract_metrics(language: str, content: str) -> dict:
    if language == 'terraform':
        from repominer.metrics.terraform import TerraformMetricsExtractor
        extractor = TerraformMetricsExtractor(
            path_to_repo='/github/workspace',
            clone_repo_to='/github/workspace',
            at='release'
        )
        return extractor.get_product_metrics(content)

    elif language == 'kubernetes':
        # Usa direttamente la funzione extract_kubernetes della tua libreria
        from kubernetes_metrics import extract_kubernetes
        return extract_kubernetes(content)


FILE_EXTENSIONS = {
    'terraform':  ('.tf',),
    'kubernetes': ('.yaml', '.yml'),
}

target_extensions = FILE_EXTENSIONS[language]
found_files = False

for file in files:
    if not file.filename.endswith(target_extensions):
        continue

    try:
        content = repo.get_contents(file.filename, ref=github_sha).decoded_content.decode()
    except Exception as e:
        print(f"⚠️ Impossibile leggere {file.filename}: {e}")
        continue

    # Per Kubernetes skippa file .yml che non sono manifest
    if language == 'kubernetes' and 'kind:' not in content:
        print(f"⏭ Skip {file.filename} (non sembra un manifest Kubernetes)")
        continue

    found_files = True
    print(f"\n--- Analisi file: {file.filename} ---")

    metrics = {}
    try:
        metrics = extract_metrics(language, content)
        print(f"📊 Metriche estratte:")
        print(json.dumps(metrics, indent=2))
    except Exception as e:
        print(f"⚠️ Errore durante l'estrazione delle metriche: {e}")
        metrics = {"syntax_error": 1}

    url = f'{url_base}/predict?model_id={model}'
    for name, value in metrics.items():
        url += f'&{name}={value}'

    headers = {"ngrok-skip-browser-warning": "true"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            res    = json.loads(response.content.decode())
            is_bad = res.get("failure_prone", False)
            icon   = "❌ DIFETTOSO" if is_bad else "✅ PULITO"
            print(f"\n{icon} | File: {file.filename}")
            print(f"Dettaglio risposta: {json.dumps(res, indent=2)}")
        else:
            print(f"❌ Errore dal backend. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print(f"⚠️ Impossibile contattare il backend: {e}")

    sys.stdout.flush()

if not found_files:
    print(f"ℹ️ Nessun file {language} trovato in questo commit.")