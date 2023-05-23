from typing import Dict, Any
from enum import Enum


class MappingOperator(Enum):
    DELETE = 1


def process_keys(d: Dict[str, Any], mapping: Dict[str, Any]) -> Dict[str, Any]:
    n: dict = {}
    for k, v in d.items():
        key = k
        # If mapping is DELETE we skip copying the key to new output dict
        if key in mapping and mapping[key] == MappingOperator.DELETE:
            continue
        # Map new mapping to output dict
        if key in mapping and not isinstance(mapping[key], MappingOperator):
            key = mapping[key]

        # Recurse into dict
        if isinstance(v, dict):
            n[key] = process_keys(v, mapping)
        # Iterate over list
        elif isinstance(v, list):
            n[key] = []
            for i in v:
                if isinstance(i, dict):
                    n[key].append(process_keys(i, mapping))
                else:
                    n[key].append(i)
        # Copy blindly
        else:
            n[key] = v
    return n
