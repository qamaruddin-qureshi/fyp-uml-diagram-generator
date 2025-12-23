"""Apply normalization to architecture_training_data.json

This script loads the training data, applies component/node/device normalization,
creates a backup, and writes the normalized version back.
"""

import json
import os
import shutil
import time
from normalize_components import normalize_training_data

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_PATH = os.path.join(ROOT, 'architecture_training_data.json')
BACKUP_DIR = os.path.join(ROOT, 'backups')


def main():
    print('Loading training data...')
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f'Loaded {len(data)} documents')
    
    # Create backup
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'architecture_training_data.json.bak.{ts}')
    shutil.copy2(DATA_PATH, backup_path)
    print(f'Backup created: {backup_path}')
    
    # Apply normalization
    print('\nNormalizing component and node names...')
    normalized_data, stats = normalize_training_data(data)
    
    # Print statistics
    print('\n' + '=' * 60)
    print('NORMALIZATION STATISTICS')
    print('=' * 60)
    print(f"Total documents processed:    {stats['total_docs']}")
    print(f"Components normalized:        {stats['components_normalized']}")
    print(f"Nodes normalized:             {stats['nodes_normalized']}")
    print(f"Devices normalized:           {stats['devices_normalized']}")
    print(f"Environments normalized:      {stats['environments_normalized']}")
    print(f"Total normalizations:         {sum([stats[k] for k in stats if k != 'total_docs'])}")
    print('=' * 60)
    
    # Write normalized data
    print(f'\nWriting normalized data to {DATA_PATH}...')
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(normalized_data, f, indent=2)
    
    print('✅ Normalization complete!')
    print(f'\nBackup available at: {backup_path}')


if __name__ == '__main__':
    main()
