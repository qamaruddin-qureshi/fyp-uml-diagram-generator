"""Configuration loader for normalization rules.

Loads normalization rules from normalization_config.json and provides
an interface to check which rules are enabled and apply them.
"""

import json
import os
import re
from typing import Dict, Optional, List, Set

class NormalizationConfig:
    """Manages normalization configuration and rule application."""
    
    def __init__(self, config_path: str = "normalization_config.json"):
        """Load configuration from JSON file."""
        self.config_path = config_path
        self.config = self._load_config()
        self._compiled_patterns = {}
        self._build_pattern_cache()
    
    def _load_config(self) -> dict:
        """Load and validate configuration file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _build_pattern_cache(self):
        """Pre-compile regex patterns from config for performance."""
        if not self.is_enabled():
            return
        
        # Build component patterns
        if self.config.get('component_rules', {}).get('enabled'):
            self._compiled_patterns['components'] = self._build_patterns_for_category('component_rules')
        
        # Build node patterns
        if self.config.get('node_rules', {}).get('enabled'):
            self._compiled_patterns['nodes'] = self._build_patterns_for_category('node_rules')
        
        # Build device patterns
        if self.config.get('device_rules', {}).get('enabled'):
            self._compiled_patterns['devices'] = self._build_patterns_for_category('device_rules')
        
        # Build environment patterns
        if self.config.get('environment_rules', {}).get('enabled'):
            self._compiled_patterns['environments'] = self._build_patterns_for_environment()
        
        # Build interface patterns
        if self.config.get('interface_rules', {}).get('enabled'):
            self._compiled_patterns['interfaces'] = self._build_patterns_for_interface()
        
        # Build external system patterns
        if self.config.get('external_system_rules', {}).get('enabled'):
            self._compiled_patterns['external_systems'] = self._build_patterns_for_external()
    
    def _build_patterns_for_category(self, category: str) -> Dict[str, str]:
        """Build regex patterns for a category (components, nodes, devices)."""
        patterns = {}
        category_config = self.config.get(category, {})
        
        for group_name, group_config in category_config.get('patterns', {}).items():
            if not isinstance(group_config, dict) or not group_config.get('enabled', True):
                continue
            
            for canonical, variants in group_config.items():
                if canonical == 'enabled':
                    continue
                
                if isinstance(variants, list) and variants:
                    # Build regex pattern from variants
                    escaped_variants = [re.escape(v) for v in variants]
                    pattern = r'\b(?:' + '|'.join(escaped_variants) + r')\b'
                    # Use canonical name with proper casing
                    canonical_name = canonical.replace('_', ' ').title()
                    patterns[pattern] = canonical_name
        
        return patterns
    
    def _build_patterns_for_environment(self) -> Dict[str, str]:
        """Build patterns for environments."""
        patterns = {}
        env_config = self.config.get('environment_rules', {})
        
        if not env_config.get('enabled'):
            return patterns
        
        for canonical, variants in env_config.get('patterns', {}).items():
            if isinstance(variants, list) and variants:
                escaped_variants = [re.escape(v) for v in variants]
                pattern = r'\b(?:' + '|'.join(escaped_variants) + r')\b'
                canonical_name = canonical.replace('_', ' ').title() if '_' in canonical else canonical.upper()
                patterns[pattern] = canonical_name
        
        return patterns
    
    def _build_patterns_for_interface(self) -> Dict[str, str]:
        """Build patterns for interfaces."""
        patterns = {}
        interface_config = self.config.get('interface_rules', {})
        
        if not interface_config.get('enabled'):
            return patterns
        
        for canonical, variants in interface_config.get('patterns', {}).items():
            if isinstance(variants, list) and variants:
                escaped_variants = [re.escape(v) for v in variants]
                pattern = r'\b(?:' + '|'.join(escaped_variants) + r')\b'
                canonical_name = canonical.replace('_', ' ').title()
                patterns[pattern] = canonical_name
        
        return patterns
    
    def _build_patterns_for_external(self) -> Dict[str, str]:
        """Build patterns for external systems."""
        patterns = {}
        external_config = self.config.get('external_system_rules', {})
        
        if not external_config.get('enabled'):
            return patterns
        
        for canonical, variants in external_config.get('patterns', {}).items():
            if isinstance(variants, list) and variants:
                escaped_variants = [re.escape(v) for v in variants]
                pattern = r'\b(?:' + '|'.join(escaped_variants) + r')\b'
                # Special handling for known brands
                if canonical in ['stripe', 'paypal', 'twilio', 'sendgrid']:
                    canonical_name = canonical.title()
                elif canonical == 'aws_s3':
                    canonical_name = 'AWS S3'
                elif canonical == 'aws_lambda':
                    canonical_name = 'AWS Lambda'
                else:
                    canonical_name = canonical.replace('_', ' ').title()
                patterns[pattern] = canonical_name
        
        return patterns
    
    def is_enabled(self) -> bool:
        """Check if normalization is globally enabled."""
        return self.config.get('enabled', True)
    
    def should_remove_articles(self) -> bool:
        """Check if article removal is enabled."""
        return self.config.get('policies', {}).get('remove_articles', True)
    
    def should_normalize_whitespace(self) -> bool:
        """Check if whitespace normalization is enabled."""
        return self.config.get('policies', {}).get('normalize_whitespace', True)
    
    def should_apply_title_case(self) -> bool:
        """Check if title case should be applied."""
        return self.config.get('policies', {}).get('apply_title_case', True)
    
    def should_apply_patterns(self) -> bool:
        """Check if pattern matching is enabled."""
        return self.config.get('policies', {}).get('apply_patterns', True)
    
    def is_case_sensitive(self) -> bool:
        """Check if pattern matching should be case sensitive."""
        return self.config.get('policies', {}).get('case_sensitive_matching', False)
    
    def get_strictness(self) -> str:
        """Get normalization strictness level: strict, moderate, minimal."""
        return self.config.get('strictness', 'moderate')
    
    def apply_patterns(self, text: str, category: str) -> Optional[str]:
        """Apply patterns for a specific category and return canonical name if matched.
        
        Prioritizes longer/more specific matches over shorter ones.
        """
        if not self.should_apply_patterns():
            return None
        
        patterns = self._compiled_patterns.get(category, {})
        if not patterns:
            return None
        
        text_lower = text.lower() if not self.is_case_sensitive() else text
        
        # Find ALL matching patterns, then pick the best one (longest match)
        matches = []
        for pattern, canonical in patterns.items():
            flags = re.IGNORECASE if not self.is_case_sensitive() else 0
            match = re.search(pattern, text_lower, flags)
            if match:
                # Score by match length (longer = more specific = better)
                match_length = match.end() - match.start()
                matches.append((match_length, canonical, match.group()))
        
        if matches:
            # Return the canonical name of the longest match
            matches.sort(key=lambda x: x[0], reverse=True)
            return matches[0][1]
        
        return None
    
    def is_deduplication_enabled(self) -> bool:
        """Check if deduplication is enabled."""
        return self.config.get('deduplication', {}).get('enabled', True)
    
    def is_cross_collection_deduplication_enabled(self) -> bool:
        """Check if cross-collection deduplication is enabled."""
        return self.config.get('deduplication', {}).get('cross_collection_deduplication', {}).get('enabled', True)
    
    def get_cross_collection_rules(self) -> List[Dict]:
        """Get cross-collection deduplication rules."""
        return self.config.get('deduplication', {}).get('cross_collection_deduplication', {}).get('rules', [])


# Global config instance
_config_instance = None

def get_config() -> NormalizationConfig:
    """Get or create the global config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = NormalizationConfig()
    return _config_instance

def reload_config():
    """Reload configuration from file."""
    global _config_instance
    _config_instance = NormalizationConfig()
