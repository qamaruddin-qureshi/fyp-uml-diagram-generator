"""Component and Node normalization utilities.

POST-EXTRACTION NORMALIZATION for NER outputs.

This module provides normalization functions to deduplicate component/node/device names
AFTER the NER model extracts them. The model extracts raw entity spans, and these functions
normalize them to canonical forms.

Architecture:
    User Input → NER Model → Raw Entities → normalize_*() → Canonical Names → Diagrams

Configuration:
    Edit normalization_config.json to control:
    - Enable/disable specific normalization rules
    - Set normalization strictness (strict/moderate/minimal)
    - Add custom technology mappings
    - Control case sensitivity and article removal

Key Functions:
    - normalize_component_name(): Normalize components, services, databases, caches
    - normalize_node_name(): Normalize servers, VMs, containers
    - normalize_device_name(): Normalize browsers, mobile devices, clients
    - normalize_environment_name(): Normalize runtime environments
    - normalize_external_system(): Normalize third-party integrations
    - normalize_interface(): Normalize API interfaces

Usage:
    from scripts.normalize_components import normalize_component_name
    
    raw_entity = "External Stripe Payment Gateway"  # From NER model
    canonical = normalize_component_name(raw_entity)
    # Returns: "Stripe Gateway"
    
    # To reload config after editing normalization_config.json:
    from scripts.normalize_components import reload_config
    reload_config()
"""

import re
from typing import Dict, Set, Optional
from scripts.normalization_config_loader import get_config


# ============================================================================
# HARDCODED CANONICAL MAPPINGS (Fast exact/regex matching)
# These provide performance and reliability - tried and tested patterns
# ============================================================================

CANONICAL_COMPONENTS = {
    # Payment gateways
    r'\b(external\s+)?stripe(\s+payment)?(\s+gateway)?\b': 'Stripe Gateway',
    r'\b(external\s+)?paypal(\s+payment)?(\s+gateway)?\b': 'PayPal',
    
    # Databases
    r'\b(a\s+|the\s+)?postgresql(\s+database|\s+db)?\b': 'PostgreSQL',
    r'\b(a\s+|the\s+)?postgres(\s+database|\s+db)?\b': 'PostgreSQL',
    r'\b(a\s+|the\s+)?mysql(\s+database|\s+db)?\b': 'MySQL',
    r'\b(a\s+|the\s+)?mongo(db)?(\s+database|\s+db)?\b': 'MongoDB',
    r'\bredis(\s+cache|\s+db)?\b': 'Redis',
    
    # Services
    r'\bbackend(\s+service(s)?|\s+api)?\b': 'Backend Service',
    r'\b(rest|restful)(\s+api)?\b': 'REST API',
    r'\bgraphql(\s+api)?\b': 'GraphQL API',
}

CANONICAL_NODES = {
    # Database servers (when used as deployment nodes) - MUST come before generic "server"
    r'\b(a\s+|the\s+)?postgresql(\s+database|\s+db|\s+server)?\b': 'PostgreSQL',
    r'\b(a\s+|the\s+)?postgres(\s+database|\s+db|\s+server)?\b': 'PostgreSQL',
    r'\b(a\s+|the\s+)?mysql(\s+database|\s+db|\s+server)?\b': 'MySQL',
    r'\b(a\s+|the\s+)?mongo(db)?(\s+database|\s+db|\s+server)?\b': 'MongoDB',
    
    # Containers
    r'\b(in\s+|on\s+)?docker\s+container(s)?\b': 'Docker Container',
    r'\bkubernetes(\s+pod(s)?|\s+cluster)?\b': 'Kubernetes',
    
    # Specific servers
    r'\blinux\s+server(s)?\b': 'Linux Server',
    
    # Generic server (MUST be last - catches anything not matched above)
    r'\bserver(\s+instance)?(s)?\b': 'Server',
}

CANONICAL_DEVICES = {
    # Browsers
    r'\b(via\s+|through\s+)?web\s+browser(s)?\b': 'Web Browser',
    r'\b(via\s+|through\s+)?mobile\s+browser(s)?\b': 'Mobile Browser',
    r'\b(via\s+|through\s+)?desktop\s+browser(s)?\b': 'Web Browser',
    r'\bbrowser(s)?\b': 'Web Browser',
    
    # Devices
    r'\b(and\s+|via\s+)?mobile\s+(device(s)?|application(s)?)\b': 'Mobile Device',
    r'\bsmartphone(s)?\b': 'Smartphone',
    r'\bdesktop\s+(client(s)?|computer(s)?)\b': 'Desktop',
}

CANONICAL_ENVIRONMENTS = {
    r'\bdocker(\s+container)?\b': 'Docker',
    r'\bkubernetes\b': 'Kubernetes',
    r'\bk8s\b': 'Kubernetes',
}

CANONICAL_INTERFACES = {
    r'\brest(\s+api|\s+endpoint(s)?)?\b': 'REST API',
    r'\bgraphql(\s+api|\s+endpoint)?\b': 'GraphQL API',
    r'\bgrpc(\s+service)?\b': 'gRPC',
}

CANONICAL_EXTERNAL_SYSTEMS = {
    r'\bstripe\b': 'Stripe',
    r'\bpaypal\b': 'PayPal',
    r'\btwilio\b': 'Twilio',
}


def _apply_canonical_map(name: str, mapping: Dict[str, str]) -> Optional[str]:
    """Apply hardcoded canonical mappings (fast path)."""
    name_lower = name.lower().strip()
    for pattern, canonical in mapping.items():
        if re.search(pattern, name_lower, re.IGNORECASE):
            return canonical
    return None


def _clean_text(text: str) -> str:
    """Basic text cleaning: remove articles, extra spaces, normalize case."""
    if not text:
        return ''
    
    config = get_config()
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Remove common articles at start (if enabled)
    if config.should_remove_articles():
        text = re.sub(r'^(the|a|an)\s+', '', text, flags=re.IGNORECASE)
        # Remove "and" connectors that create duplicates (e.g., "And Mobile")
        text = re.sub(r'^and\s+', '', text, flags=re.IGNORECASE)
        # Remove "and" at the end too (e.g., "Web Browser And")
        text = re.sub(r'\s+and$', '', text, flags=re.IGNORECASE)
        # Remove prepositions like "via", "through", "in", "on" at start
        text = re.sub(r'^(via|through|in|on)\s+', '', text, flags=re.IGNORECASE)
    
    # Normalize whitespace (if enabled)
    if config.should_normalize_whitespace():
        text = re.sub(r'\s+', ' ', text)
    
    # Title case for consistency (if enabled)
    if config.should_apply_title_case():
        text = text.title()
    
    return text.strip()


def normalize_component_name(name: str) -> str:
    """Normalize a component name to its canonical form.
    
    Uses BOTH hardcoded patterns (fast) AND normalization_config.json (flexible).
    Edit the config file to add custom patterns without touching code.
    
    Args:
        name: Raw component name from NER extraction
        
    Returns:
        Canonical component name
    
    Examples:
        >>> normalize_component_name("External Stripe Payment Gateway")
        'Stripe Gateway'
        >>> normalize_component_name("  Backend Service  ")
        'Backend Service'
        >>> normalize_component_name("A PostgreSQL Database")
        'PostgreSQL'
    """
    if not name or not isinstance(name, str):
        return ''
    
    # Strategy 1: Try hardcoded patterns first (fastest, most reliable)
    canonical = _apply_canonical_map(name, CANONICAL_COMPONENTS)
    if canonical:
        return canonical
    
    # Strategy 2: Try config-based patterns (user-customizable)
    config = get_config()
    if config.is_enabled() and config.should_apply_patterns():
        canonical = config.apply_patterns(name, 'components')
        if canonical:
            return canonical
    
    # Strategy 3: Fallback to basic text cleaning
    return _clean_text(name)


def normalize_node_name(name: str) -> str:
    """Normalize a node/server name to its canonical form.
    
    Uses BOTH hardcoded patterns AND normalization_config.json.
    
    Args:
        name: Raw node name from extraction
        
    Returns:
        Canonical node name
        
    Examples:
        >>> normalize_node_name("In Docker Containers")
        'Docker Container'
        >>> normalize_node_name("A Linux Server")
        'Linux Server'
    """
    if not name or not isinstance(name, str):
        return ''
    
    # Try hardcoded patterns first
    canonical = _apply_canonical_map(name, CANONICAL_NODES)
    if canonical:
        return canonical
    
    # Try config patterns
    config = get_config()
    if config.is_enabled() and config.should_apply_patterns():
        canonical = config.apply_patterns(name, 'nodes')
        if canonical:
            return canonical
    
    # Fallback to cleaning
    return _clean_text(name)


def normalize_device_name(name: str) -> str:
    """Normalize a device name to its canonical form.
    
    Uses BOTH hardcoded patterns AND normalization_config.json.
    
    Args:
        name: Raw device name from extraction
        
    Returns:
        Canonical device name
        
    Examples:
        >>> normalize_device_name("The User's Mobile Phone")
        'Mobile Device'
        >>> normalize_device_name("A Web Browser")
        'Web Browser'
    """
    if not name or not isinstance(name, str):
        return ''
    
    # Try hardcoded patterns first
    canonical = _apply_canonical_map(name, CANONICAL_DEVICES)
    if canonical:
        return canonical
    
    # Try config patterns
    config = get_config()
    if config.is_enabled() and config.should_apply_patterns():
        canonical = config.apply_patterns(name, 'devices')
        if canonical:
            return canonical
    
    # Fallback to cleaning
    return _clean_text(name)


def normalize_environment_name(name: str) -> str:
    """Normalize an environment/runtime name to its canonical form.
    
    Uses BOTH hardcoded patterns AND normalization_config.json.
    
    Args:
        name: Raw environment name from extraction
        
    Returns:
        Canonical environment name
        
    Examples:
        >>> normalize_environment_name("In Production Env")
        'Production'
        >>> normalize_environment_name("The Dev Environment")
        'Development'
    """
    if not name or not isinstance(name, str):
        return ''
    
    # Try hardcoded patterns first
    canonical = _apply_canonical_map(name, CANONICAL_ENVIRONMENTS)
    if canonical:
        return canonical
    
    # Try config patterns
    config = get_config()
    if config.is_enabled() and config.should_apply_patterns():
        canonical = config.apply_patterns(name, 'environments')
        if canonical:
            return canonical
    
    # Fallback to cleaning
    return _clean_text(name)


def normalize_interface(name: str) -> str:
    """Normalize an interface name to its canonical form.
    
    Uses BOTH hardcoded patterns AND normalization_config.json.
    
    Args:
        name: Raw interface name from extraction
        
    Returns:
        Canonical interface name
    
    Examples:
        >>> normalize_interface("REST endpoint")
        'REST API'
        >>> normalize_interface("GraphQL API")
        'GraphQL API'
    """
    if not name or not isinstance(name, str):
        return ''
    
    # Try hardcoded patterns first
    canonical = _apply_canonical_map(name, CANONICAL_INTERFACES)
    if canonical:
        return canonical
    
    # Try config patterns
    config = get_config()
    if config.is_enabled() and config.should_apply_patterns():
        canonical = config.apply_patterns(name, 'interfaces')
        if canonical:
            return canonical
    
    # Fallback to cleaning
    return _clean_text(name)


def normalize_external_system(name: str) -> str:
    """Normalize an external system name to its canonical form.
    
    Uses BOTH hardcoded patterns AND normalization_config.json.
    
    Args:
        name: Raw external system name from extraction
        
    Returns:
        Canonical external system name
    
    Examples:
        >>> normalize_external_system("External Stripe")
        'Stripe'
        >>> normalize_external_system("The Twilio API")
        'Twilio'
    """
    if not name or not isinstance(name, str):
        return ''
    
    # Try hardcoded patterns first
    canonical = _apply_canonical_map(name, CANONICAL_EXTERNAL_SYSTEMS)
    if canonical:
        return canonical
    
    # Try config patterns
    config = get_config()
    if config.is_enabled() and config.should_apply_patterns():
        canonical = config.apply_patterns(name, 'external_systems')
        if canonical:
            return canonical
    
    # Fallback to cleaning
    return _clean_text(name)


def normalize_training_data(data: list) -> tuple[list, dict]:
    """Normalize all component/node names in training data.
    
    Args:
        data: List of training documents
        
    Returns:
        Tuple of (normalized_data, stats_dict)
        stats_dict contains counts of normalizations performed
    """
    stats = {
        'components_normalized': 0,
        'nodes_normalized': 0,
        'devices_normalized': 0,
        'environments_normalized': 0,
        'total_docs': len(data)
    }
    
    for doc in data:
        if not isinstance(doc, dict):
            continue
        
        # Normalize components
        arch_out = doc.get('architecture_output', {})
        if arch_out and 'components' in arch_out:
            components = arch_out['components']
            if isinstance(components, list):
                for comp in components:
                    if isinstance(comp, dict) and 'name' in comp:
                        original = comp['name']
                        normalized = normalize_component_name(original)
                        if normalized != original:
                            comp['name'] = normalized
                            stats['components_normalized'] += 1
        
        # Normalize deployment elements
        dep_out = doc.get('deployment_output', {})
        if dep_out:
            # Nodes
            if 'nodes' in dep_out and isinstance(dep_out['nodes'], list):
                for node in dep_out['nodes']:
                    if isinstance(node, dict) and 'name' in node:
                        original = node['name']
                        normalized = normalize_node_name(original)
                        if normalized != original:
                            node['name'] = normalized
                            stats['nodes_normalized'] += 1
            
            # Devices
            if 'devices' in dep_out and isinstance(dep_out['devices'], list):
                for device in dep_out['devices']:
                    if isinstance(device, dict) and 'name' in device:
                        original = device['name']
                        normalized = normalize_device_name(original)
                        if normalized != original:
                            device['name'] = normalized
                            stats['devices_normalized'] += 1
            
            # Environments
            if 'environments' in dep_out and isinstance(dep_out['environments'], list):
                for env in dep_out['environments']:
                    if isinstance(env, dict) and 'name' in env:
                        original = env['name']
                        normalized = normalize_environment_name(original)
                        if normalized != original:
                            env['name'] = normalized
                            stats['environments_normalized'] += 1
    
    return data, stats


if __name__ == '__main__':
    # Test examples
    test_components = [
        "External Stripe Payment Gateway",
        "Stripe Payment",
        "A PostgreSQL Database",
        "Backend Service",
        "Service API",
        "EcommerceFrontend",
        "Ecommerce Frontend",
        "REST API",
        "GraphQL endpoint",
    ]
    
    print("Component Normalization Tests:")
    print("-" * 60)
    for comp in test_components:
        normalized = normalize_component_name(comp)
        print(f"{comp:40} -> {normalized}")
    
    print("\n" + "=" * 60 + "\n")
    
    test_nodes = [
        "In Docker Containers",
        "Docker Container",
        "A Linux Server",
        "Linux Server",
        "Ubuntu Server",
        "Virtual Machine",
        "EC2 Instance",
        "Kubernetes cluster",
    ]
    
    print("Node Normalization Tests:")
    print("-" * 60)
    for node in test_nodes:
        normalized = normalize_node_name(node)
        print(f"{node:40} -> {normalized}")
    
    print("\n" + "=" * 60 + "\n")
    
    test_devices = [
        "Via Web Browser",
        "Web Browsers",
        "Web Browser",
        "And Mobile Devices",
        "Mobile Device",
        "Smartphone",
        "IoT devices",
    ]
    
    print("Device Normalization Tests:")
    print("-" * 60)
    for device in test_devices:
        normalized = normalize_device_name(device)
        print(f"{device:40} -> {normalized}")
    
    print("\n" + "=" * 60 + "\n")
    
    test_externals = [
        "External Stripe",
        "The PayPal API",
        "Twilio service",
        "AWS S3",
    ]
    
    print("External System Normalization Tests:")
    print("-" * 60)
    for ext in test_externals:
        normalized = normalize_external_system(ext)
        print(f"{ext:40} -> {normalized}")
