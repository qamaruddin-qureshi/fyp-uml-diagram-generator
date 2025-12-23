
import json
import os

def fix_json(file_path):
    print(f"Loading {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Original count: {len(data)}")
    
    new_data = []
    fixed_count = 0
    
    for item in data:
        if isinstance(item, list):
            print(f"Found nested list with {len(item)} items. Flattening...")
            new_data.extend(item)
            fixed_count += 1
        else:
            new_data.append(item)
            
    print(f"New count: {len(new_data)}")
    
    if fixed_count > 0:
        print("Saving fixed data...")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=2)
        print("Done.")
    else:
        print("No issues found.")

if __name__ == "__main__":
    fix_json("architecture_training_data.json")
