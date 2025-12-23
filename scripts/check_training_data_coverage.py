"""Check training data for documents with both component and deployment data."""
import json

with open('architecture_training_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find documents with both
both_docs = []
component_only = []
deployment_only = []
neither = []

for i, item in enumerate(data):
    if not isinstance(item, dict):
        continue
    
    arch_output = item.get('architecture_output', {})
    deploy_output = item.get('deployment_output', {})
    
    has_components = len(arch_output.get('components', [])) > 0
    has_nodes = len(deploy_output.get('nodes', [])) > 0
    
    if has_components and has_nodes:
        both_docs.append(i)
    elif has_components:
        component_only.append(i)
    elif has_nodes:
        deployment_only.append(i)
    else:
        neither.append(i)

print("="*70)
print("TRAINING DATA ANALYSIS: Component vs Deployment")
print("="*70)
print(f"\n📊 Document Distribution:")
print(f"   Total documents: {len(data)}")
print(f"   ✅ BOTH component + deployment: {len(both_docs)} ({len(both_docs)/len(data)*100:.1f}%)")
print(f"   🔵 Component only: {len(component_only)} ({len(component_only)/len(data)*100:.1f}%)")
print(f"   🟢 Deployment only: {len(deployment_only)} ({len(deployment_only)/len(data)*100:.1f}%)")
print(f"   ⚪ Neither: {len(neither)} ({len(neither)/len(data)*100:.1f}%)")

# Show example with both
if both_docs:
    print(f"\n{'='*70}")
    print("EXAMPLE: Document with BOTH Component + Deployment Data")
    print(f"{'='*70}\n")
    
    idx = both_docs[0]
    item = data[idx]
    
    arch_narration = item['architecture_narration']['text']
    arch_output = item['architecture_output']
    deploy_output = item['deployment_output']
    
    print(f"Document Index: {idx}\n")
    print(f"Architecture Narration (first 400 chars):")
    print(f"{arch_narration[:400]}...\n")
    
    print(f"Component Diagram Data:")
    print(f"  • Components: {len(arch_output.get('components', []))}")
    for comp in arch_output.get('components', [])[:3]:
        print(f"    - {comp.get('name', 'N/A')}")
    
    print(f"  • External Systems: {len(arch_output.get('external_systems', []))}")
    for ext in arch_output.get('external_systems', [])[:3]:
        print(f"    - {ext.get('name', 'N/A') if isinstance(ext, dict) else ext}")
    
    print(f"  • Relationships: {len(arch_output.get('relationships', []))}")
    for rel in arch_output.get('relationships', [])[:3]:
        print(f"    - {rel.get('from')} -> {rel.get('to')} ({rel.get('relation')})")
    
    print(f"\nDeployment Diagram Data:")
    print(f"  • Nodes: {len(deploy_output.get('nodes', []))}")
    for node in deploy_output.get('nodes', [])[:3]:
        print(f"    - {node.get('name', 'N/A')} ({node.get('type', 'N/A')})")
    
    print(f"  • Devices: {len(deploy_output.get('devices', []))}")
    for dev in deploy_output.get('devices', [])[:3]:
        print(f"    - {dev.get('name', 'N/A') if isinstance(dev, dict) else dev}")
    
    print(f"  • Artifacts: {len(deploy_output.get('artifacts', []))}")
    print(f"  • Environments: {len(deploy_output.get('environments', []))}")

print(f"\n{'='*70}\n")
