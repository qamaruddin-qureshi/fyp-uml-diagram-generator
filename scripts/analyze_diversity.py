
import json
import re
from collections import Counter

def analyze_diversity():
    print("Loading architecture_training_data.json...")
    try:
        with open('architecture_training_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("File not found.")
        return

    keywords = {
        # Messaging / Event Driven
        "queue": 0, "topic": 0, "broker": 0, "rabbitmq": 0, "kafka": 0, "event bus": 0,
        "pub/sub": 0, "message": 0, "stream": 0,
        
        # Layered / Patterns
        "layer": 0, "tier": 0, "mvc": 0, "gateway": 0, "pipeline": 0, "filter": 0,
        
        # Microservices / Cloud
        "microservice": 0, "serverless": 0, "lambda": 0, "function": 0, "k8s": 0, "mesh": 0,
        
        # Specific Technologies representing patterns
        "graphql": 0, "grpc": 0, "soap": 0, "rest": 0, 
        
        # Blockchain/Decentralized (Case 14)
        "blockchain": 0, "ethereum": 0, "wallet": 0, "decentralized": 0
    }
    
    total_docs = 0
    
    for item in data:
        narration = item.get("architecture_narration")
        if not narration: continue
        text = narration.get("text", "") if isinstance(narration, dict) else str(narration)
        text_lower = text.lower()
        
        total_docs += 1
        for key in keywords:
            if key in text_lower:
                keywords[key] += 1
                
    print(f" Analyzed {total_docs} documents.")
    print("\n--- Keyword Frequency ---")
    for key, count in sorted(keywords.items(), key=lambda item: item[1], reverse=True):
        if count > 0:
            print(f"{key}: {count} ({count/total_docs*100:.2f}%)")
    
if __name__ == "__main__":
    analyze_diversity()
