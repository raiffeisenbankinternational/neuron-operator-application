# Copied and heavily modified from dollar-ref under MIT License
# https://github.com/bagrat/dollar-ref
import os
import json
import yaml
from typing import Any, Optional, Tuple, Dict
from dotty_dict import Dotty


class ResolutionError(Exception):
    """
    General error that happens during resolution.
    """

    pass


class InternalResolutionError(ResolutionError):
    """
    Error while resolving internal referenses.
    """

    pass


class FileResolutionError(ResolutionError):
    """
    Error while resolving a reference to another file.
    """

    pass


class DecodeError(ResolutionError):
    """
    Error while deciding a referenced file.
    """

    pass


# Recursively look for $refs in a dict and copy external refs
# over to our local dict.
#
# Before:
# definitions:
#   MyDefinition:
#     $ref: 'another_file.yaml#/definitions/AnotherDefinition'
#
# After:
# definitions:
#   AnotherDefinition:
#     type: object
#     properties:
#       name:
#         type: string
#   MyDefinition:
#     $ref: '#/definitions/AnotherDefinition'
def slurp(data: dict, cwd: str) -> dict:
    data, copies = slurp_refs(data, cwd)
    # Use Dotty with separator='/' to easily set nested values
    # with nested/key instead of the default nested.key
    dot = Dotty(data, separator="/")
    for key, value in copies.items():
        dot[key.lstrip("/")] = value
    return dot.to_dict()


def slurp_refs(
    data: dict, cwd: str, root: Optional[dict] = None, copies: Optional[dict] = None
) -> Tuple[Any, Dict[str, Any]]:
    if copies == None:
        copies = {}

    if not isinstance(data, dict):
        if isinstance(data, list):
            for i, item in enumerate(data):
                data[i], copies = slurp_refs(item, cwd, root, copies)
        return data, copies

    # Recursively go through dict until we find a $ref
    if "$ref" not in data:
        for subkey in data:
            data[subkey], copies = slurp_refs(data[subkey], cwd, root, copies)
        return data, copies

    ref = data["$ref"]
    res = data.get("resolve", False)

    # If ref does not start with '#' it is an external ref
    # NOTE: http ref is not supported yet
    if not ref.startswith("#"):
        if res:
            return slurp_ref_file(ref, cwd, copies)
        else:
            d, copies = slurp_ref_file(ref, cwd, copies)
            _, in_ref = ref.split("#")
            data["$ref"] = f"#{in_ref}"
            copies[in_ref] = d
    # If root is not None we're inside of an external ref
    # and we want to copy all of their internal refs over
    elif root != None:
        d = _follow_path(ref, root)
        copies[ref.lstrip("#")] = d

    return data, copies


def slurp_ref_file(
    ref: str, cwd: str, copies: Dict[str, Any]
) -> Tuple[Any, Dict[str, Any]]:
    path, in_ref = ref.split("#")

    if in_ref == None:
        in_ref = ""

    in_ref = f"#{in_ref}"

    if not os.path.isabs(path):
        path = os.path.join(cwd, path)

    try:
        file_data = read_file(path)
    except FileNotFoundError:
        raise FileResolutionError(
            f"Could not resolve '{ref}', " f"'{path}' file not found."
        )

    data = _follow_path(in_ref, file_data)

    new_cwd = os.path.dirname(path)

    return slurp_refs(data, new_cwd, file_data, copies)


# Unmodified
def _follow_path(ref: str, data: dict) -> dict:
    """
    Returns the object from `data` at `ref`.
    Example:
        Given:
            data = {
                'key1': {
                    'key2': 'value'
                }
            }
            ref = '#/key1/key2'
        The result will be:
            'value'
    """
    if ref in ("", "#", "#/"):
        return data

    ref_path = ref[2:].split("/")

    ref_data = data
    for path_item in ref_path:
        try:
            ref_data = ref_data[path_item]
        except KeyError:
            raise InternalResolutionError(
                f"Error resolving '{ref}', " f"'{path_item}' not found in '{ref_data}'."
            )

    return ref_data


# unmodified
def read_file(path: str) -> dict:
    """
    Read and decode a file specified by `path`.
    This function automatically detects whether the file is a JSON or YAML
    and decodes accordingly.
    Detection is based on the filename with files ending in .yml or yaml
    loaded as yaml. Yaml file contents may begin with ---
    http://yaml.org/spec/1.0/#id2561718 therefore
    this is another possible criterion. Any data not fitting these criteria
    is parsed as JSON.
    """
    with open(path, "r") as file:
        raw = file.read()
        if raw.startswith("---") or any(
            [path.lower().endswith(s) for s in [".yaml", ".yml"]]
        ):
            try:
                data = yaml.load(raw, Loader=yaml.FullLoader)
            except yaml.YAMLError as exc:
                raise DecodeError(f"Error decoding '{path}' file.") from exc
        else:
            try:
                data = json.loads(raw)
            except json.decoder.JSONDecodeError as exc:
                raise DecodeError(f"Error decoding '{path}' file.") from exc
    return data
