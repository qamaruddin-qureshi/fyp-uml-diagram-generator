"""Safe generator for architecture training documents.

This script appends new documents up to a TARGET_TOTAL (default 10,000).
- Maintains a distribution between BOTH / component-only / deployment-only.
- Avoids exact duplicates and near-duplicates using normalized text + token Jaccard.
- Creates a timestamped backup before editing the file.

Run as:
    python scripts/generate_training_docs.py

Adjust TARGET_TOTAL and DISTRIBUTION constants below as needed.
"""

import json
import os
import random
import shutil
import time
import hashlib
import re
from collections import Counter

# Config
DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'architecture_training_data.json'))
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backups'))
TARGET_TOTAL = 10000
# Distribution: fractions for BOTH, COMPONENT_ONLY, DEPLOYMENT_ONLY
DISTRIBUTION = (0.4, 0.3, 0.3)
MAX_ATTEMPTS_MULTIPLIER = 5  # max_attempts = multiplier * (to_add)
RANDOM_SEED = 42

random.seed(RANDOM_SEED)

# Normalization mappings to canonicalize common variants and reduce near-duplicates
CANONICAL_MAP = {
    r"\bstripe\b": "Stripe",
    r"\bstripe payment\b": "Stripe",
    r"\bstripe payment gateway\b": "Stripe",
    r"\bpayment gateway\b": "Payment Gateway",
    r"\bpostgresql\b": "PostgreSQL",
    r"\bpostgresql database\b": "PostgreSQL Database",
    r"\bpostgres database\b": "Postgre Database",
    r"\bpostgres\b": "Postgres",
    r"\bmongo(db)?\b": "MongoDB",
    r"\bredis\b": "Redis",
    r"\bdocker container\b": "Docker container",
}

# Small pools for template substitution (keeps language generic)
FRONTENDS = ["frontend", "client UI", "web UI", "application frontend", "mobile frontend"]
SERVICES = ["payment service", "order service", "backend service", "auth service", "api service", "messaging service", "course management service"]
DATABASES = ["PostgreSQL database", "MySQL database", "MongoDB database", "NoSQL database", "central database", "relational database"]
CACHES = ["Redis cache", "in-memory cache", "key-value cache"]
CONTAINERS = ["Docker container", "container"]
NODES = ["Linux server", "Ubuntu server", "Debian server", "Cloud VM", "Dedicated host"]
DEVICES = ["web browsers", "mobile devices", "desktop clients"]
EXTERNALS = ["Stripe", "PayPal", "External payment gateway", "OAuth provider"]
INTERFACES = ["REST endpoints", "HTTP API", "GraphQL endpoint"]

# Templates for types
TEMPLATE_BOTH = (
    "{frontend} communicates with the {service}. ",
    "The {service} accesses a {database} and uses {cache}. ",
    "The {service} runs in a {container} on a {node}. ",
    "Users access the system via {devices}. ",
    "The {service} exposes {interface}."
)

TEMPLATE_COMPONENT_ONLY = (
    "{frontend} communicates with the {service}. ",
    "The {service} accesses a {database} and uses {cache}. ",
    "The system integrates with {external}."
)

TEMPLATE_DEPLOYMENT_ONLY = (
    "The system is deployed on {node} instances running {container} environments. ",
    "Artifacts are packaged as container images. ",
    "Clients connect via {devices}."
)

# Helper functions

def load_existing_data(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise RuntimeError('Training data must be a JSON array')
    return data


def backup_file(path, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    dest = os.path.join(backup_dir, f'architecture_training_data.json.bak.{ts}')
    shutil.copy2(path, dest)
    return dest


def normalize_text(s):
    s = s.strip()
    s_norm = s.lower()
    for pat, replacement in CANONICAL_MAP.items():
        s_norm = re.sub(pat, replacement.lower(), s_norm, flags=re.IGNORECASE)
    s_norm = re.sub(r'\s+', ' ', s_norm).strip()
    return s_norm


def text_tokens(s):
    s = re.sub(r"[^a-zA-Z0-9 ]", " ", s.lower())
    toks = [t for t in s.split() if len(t) > 1]
    return set(toks)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = a.intersection(b)
    uni = a.union(b)
    return len(inter) / len(uni)


def fingerprint(item):
    narr = item.get('architecture_narration', {}).get('text', '')
    norm = normalize_text(narr)
    components = item.get('architecture_output', {}).get('components', []) or []
    comp_names = []
    for c in components:
        name = c.get('name') if isinstance(c, dict) else c
        if name:
            comp_names.append(normalize_text(name))
    key = norm + '||' + '|'.join(sorted(comp_names))
    return hashlib.sha1(key.encode('utf-8')).hexdigest()


def is_near_duplicate(narr_tokens, existing_token_sets, threshold=0.85, sample_size=500):
    """Check near-duplicates with sampling for efficiency on large datasets."""
    if len(existing_token_sets) <= sample_size:
        # Check all if dataset is small
        for tokset in existing_token_sets:
            if jaccard(narr_tokens, tokset) >= threshold:
                return True
    else:
        # Sample random subset for large datasets
        import random
        sample = random.sample(existing_token_sets, sample_size)
        for tokset in sample:
            if jaccard(narr_tokens, tokset) >= threshold:
                return True
    return False


def build_existing_index(data):
    fingerprints = set()
    narr_token_sets = []
    for item in data:
        if not isinstance(item, dict):
            continue
        fp = fingerprint(item)
        fingerprints.add(fp)
        narr = item.get('architecture_narration', {}).get('text', '')
        narr_token_sets.append(text_tokens(normalize_text(narr)))
    return fingerprints, narr_token_sets


def generate_doc(kind):
    ctx = {
        'frontend': random.choice(FRONTENDS),
        'service': random.choice(SERVICES),
        'database': random.choice(DATABASES),
        'cache': random.choice(CACHES),
        'container': random.choice(CONTAINERS),
        'node': random.choice(NODES),
        'devices': random.choice(DEVICES),
        'external': random.choice(EXTERNALS),
        'interface': random.choice(INTERFACES),
    }
    if kind == 'both':
        parts = [t.format(**ctx) for t in TEMPLATE_BOTH]
        text = ''.join(parts)
        scope = 'architecture+deployment'
        comp_list = [
            {'name': ctx['frontend'], 'type': 'component', 'source': 'architecture_narration', 'confidence': 'explicit'},
            {'name': ctx['service'], 'type': 'component', 'source': 'architecture_narration', 'confidence': 'explicit'},
            {'name': ctx['database'], 'type': 'component', 'source': 'architecture_narration', 'confidence': 'explicit'},
        ]
        deployment = {
            'nodes': [ {'name': ctx['node'], 'type': 'server', 'source': 'architecture_narration', 'confidence': 'explicit'} ],
            'artifacts': [],
            'devices': [ {'name': ctx['devices'], 'type': 'client', 'source': 'architecture_narration', 'confidence': 'explicit'} ],
            'environments': [ {'name': ctx['container'], 'type': 'container', 'source': 'architecture_narration', 'confidence': 'explicit'} ]
        }
        externals = []
    elif kind == 'component':
        parts = [t.format(**ctx) for t in TEMPLATE_COMPONENT_ONLY]
        text = ''.join(parts)
        scope = 'architecture'
        comp_list = [
            {'name': ctx['frontend'], 'type': 'component', 'source': 'architecture_narration', 'confidence': 'explicit'},
            {'name': ctx['service'], 'type': 'component', 'source': 'architecture_narration', 'confidence': 'explicit'},
            {'name': ctx['database'], 'type': 'component', 'source': 'architecture_narration', 'confidence': 'explicit'}
        ]
        deployment = { 'nodes': [], 'artifacts': [], 'devices': [], 'environments': [] }
        externals = []
    else:  # deployment-only
        parts = [t.format(**ctx) for t in TEMPLATE_DEPLOYMENT_ONLY]
        text = ''.join(parts)
        scope = 'deployment'
        comp_list = []
        deployment = {
            'nodes': [ {'name': ctx['node'], 'type': 'server', 'source': 'architecture_narration', 'confidence': 'explicit'} ],
            'artifacts': [ {'name': 'container image', 'type': 'artifact', 'source': 'architecture_narration', 'confidence': 'explicit'} ],
            'devices': [ {'name': ctx['devices'], 'type': 'client', 'source': 'architecture_narration', 'confidence': 'explicit'} ],
            'environments': [ {'name': ctx['container'], 'type': 'container', 'source': 'architecture_narration', 'confidence': 'explicit'} ]
        }
        externals = []

    item = {
        'architecture_narration': {
            'text': text.strip(),
            'constraints': { 'allowed_relationships': ["communicates with","depends on","interacts with","uses","accesses","is consumed by"] },
            'metadata': { 'provided': True, 'scope': scope }
        },
        'architecture_output': {
            'components': comp_list,
            'interfaces': [],
            'external_systems': externals,
            'technologies': [],
            'relationships': []
        },
        'deployment_output': deployment,
        'extraction_metadata': {
            'component_diagram_generated': True if kind in ('both','component') else False,
            'deployment_diagram_generated': True if kind in ('both','deployment') else False,
            'warnings': [] if kind != 'component' else ["Deployment narration not provided. Deployment diagram skipped."],
            'confidence_summary': { 'explicit': 6, 'inferred': 0 }
        }
    }
    if kind in ('both','component'):
        item['architecture_output']['relationships'] = [
            { 'from': comp_list[0]['name'], 'to': comp_list[1]['name'], 'relation': 'communicates with', 'source_sentence': f"{comp_list[0]['name']} communicates with {comp_list[1]['name']}." },
            { 'from': comp_list[1]['name'], 'to': comp_list[2]['name'], 'relation': 'accesses', 'source_sentence': f"{comp_list[1]['name']} accesses {comp_list[2]['name']}." }
        ]
    return item


def main():
    print('Loading existing data...')
    data = load_existing_data(DATA_PATH)
    current_count = len(data)
    print(f'Current documents: {current_count}')
    if current_count >= TARGET_TOTAL:
        print('Target already reached. Exiting.')
        return

    backup = backup_file(DATA_PATH, BACKUP_DIR)
    print(f'Backup created at: {backup}')

    fingerprints, narr_token_sets = build_existing_index(data)

    to_add = TARGET_TOTAL - current_count
    max_attempts = max(1000, to_add * MAX_ATTEMPTS_MULTIPLIER)
    attempts = 0
    added = 0

    num_both = int(round(to_add * DISTRIBUTION[0]))
    num_component_only = int(round(to_add * DISTRIBUTION[1]))
    num_deployment_only = to_add - (num_both + num_component_only)

    targets = [('both', num_both), ('component', num_component_only), ('deployment', num_deployment_only)]

    print(f'Will add total {to_add} docs: both={num_both}, component_only={num_component_only}, deployment_only={num_deployment_only}')

    for kind, target in targets:
        print(f'Generating kind={kind} target={target}')
        k_added = 0
        k_attempts = 0
        while k_added < target and attempts < max_attempts:
            candidate = generate_doc(kind)
            attempts += 1
            k_attempts += 1
            narr = candidate['architecture_narration']['text']
            norm = normalize_text(narr)
            tokset = text_tokens(norm)
            fp = hashlib.sha1((norm + '||' + '|'.join(sorted([normalize_text(c['name']) for c in candidate['architecture_output']['components'] if 'name' in c]))).encode('utf-8')).hexdigest()

            if fp in fingerprints:
                continue

            if is_near_duplicate(tokset, narr_token_sets, threshold=0.85):
                continue

            data.append(candidate)
            fingerprints.add(fp)
            narr_token_sets.append(tokset)
            added += 1
            k_added += 1

            if added % 100 == 0:
                print(f'Added {added}/{to_add} so far...')

            if k_attempts > target * 50 and k_added == 0:
                print(f'Warning: difficulty generating unique examples for kind={kind} after {k_attempts} attempts. Diversifying templates.')
                SERVICES.extend([f'service_{random.randint(1,9999)}' for _ in range(3)])
                FRONTENDS.extend([f'frontend_{random.randint(1,9999)}' for _ in range(3)])

        print(f'Finished kind={kind}, added {k_added} (attempts {k_attempts})')

    print(f'Writing {added} new documents to {DATA_PATH} ...')
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print('Generation complete.')
    cov_script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'check_training_data_coverage.py'))
    if os.path.exists(cov_script):
        print('Running coverage check...')
        os.system(f'python "{cov_script}"')


if __name__ == '__main__':
    main()
