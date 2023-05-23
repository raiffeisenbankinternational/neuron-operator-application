from typing import Any, List, Optional

key_mapping = {
    "tenant": "sample-tenant",
    "namespace": "sample-namespace",
}


def example_array(d: dict, key: Optional[str] = None) -> List:
    items = d.get("items")

    if isinstance(items, dict) and items.get("type") != None:
        return [example_type(items, key)]
    return []


def example_type(d: dict, key: Optional[str] = None) -> Any:
    tp = d.get("type")

    if key != None and key in key_mapping:
        return key_mapping[key]

    if tp == "string":
        en = d.get("enum")
        if en != None and isinstance(en, list):
            return en[0]
        return "string"
    elif tp == "boolean":
        return False
    elif tp == "integer":
        return 10
    elif tp == "number":
        return 10.0
    elif tp == "object":
        return build_example_crd(d, key)
    return None


def build_example_crd(d: dict, key: Optional[str] = None) -> Any:
    if not isinstance(d, dict):
        return None

    tp = d.get("type")
    if tp == None:
        return None

    if tp == "array":
        return example_array(d, key)
    elif tp != "object":
        return example_type(d, key)
    else:
        ret = {}
        props = d.get("properties")
        if props == None:
            props = d.get("additionalProperties")

        if isinstance(props, dict):
            if props.get("type") == "array":
                return example_array(props, key)
            if props.get("type") == "object":
                return build_example_crd(props, key)

            for prop, val in props.items():
                ret[prop] = build_example_crd(val, prop)
            return ret
    return None
