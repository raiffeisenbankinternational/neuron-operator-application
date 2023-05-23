import pathlib
import os
import yaml
import json
from lib.dref import slurp
from lib.util import MappingOperator, process_keys
from mergedeep import merge
from typing import Dict, Optional
from humps.main import is_snakecase, camelize
from datamodel_code_generator import InputFileType, PythonVersion, generate

CURRENT_VERSION = "v1alpha1"

ROOT_DIR: str = str(pathlib.Path(__file__).parent.parent)
API_ROOT: str = f"{ROOT_DIR}/apis/{CURRENT_VERSION}"

IN_FILE: str = f"{API_ROOT}/pulsar.yaml"
OUT_FILE: str = f"{ROOT_DIR}/operator/models/gen.py"

# We use 'schema' as a property in NeuronSchema but it
# is a already used attribute in Pydantic so we have to
# set it to 'schema_' with an alias of 'schema' in
# build_alias_map. All props in forbidden_props will be
# aliased as '{prop}_'.
forbidden_props = ["schema"]

# Builds an alias map for datamodel-code-generator.
# It is used to create an alias mapping between snake_case
# and camelCase fields. So both can be used as inputs to
# the models.
def build_alias_map(
    data: dict, alias_map: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    if alias_map == None:
        alias_map = {}

    if not isinstance(data, dict):
        return alias_map

    if "properties" in data:
        for prop in data["properties"]:
            if is_snakecase(prop):
                alias_map[prop] = camelize(prop)
            if prop in forbidden_props:
                alias_map[prop] = f"{prop}_"

    for subkey in data:
        alias_map = build_alias_map(data[subkey], alias_map)

    return alias_map


# Final object used for generating the model
data: Dict[str, Dict[str, dict]] = {"definitions": {}, "overrides": {}}

# Iterate through all ya?ml files in API_ROOT and merging them into
# one object
dir = os.fsencode(API_ROOT)
for file in os.listdir(dir):
    filename = os.fsdecode(file)
    if filename.endswith(".yaml") or filename.endswith(".yml"):
        print(f"Processing {filename}")
        # Read and parse file
        with open(f"{API_ROOT}/{filename}") as f:
            d = yaml.safe_load(f.read())

        if d.get("overrides"):
            for key, value in d["overrides"].items():
                data["overrides"][key] = value

        if d.get("definitions"):
            for key, value in d["definitions"].items():
                data["definitions"][key] = value

# Resolve external $refs by copying the objects and making
# it an internal $ref.
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
#
# We do this so datamodel-code-generator can re-use the same
# generated class whenever models use the same reference.
# This is ugly if we recursively resolve all references first.
data = slurp(data, API_ROOT)

# Loop over definitions in overrides and merge it with the
# same key in definitions.
if (
    data.get("overrides")
    and isinstance(data["overrides"], dict)
    and data.get("definitions")
):
    for key in data["overrides"].keys():
        if key not in data["definitions"]:
            continue

        data["definitions"][key] = dict(
            merge(data["definitions"][key], data["overrides"][key])
        )
    # Remove overrides from final object
    data.pop("overrides")

# Build an alias map from camelCase to snake_case
# We do this so the kubernetes object can be in camelCase and
# pydantic can automatically parse it and convert to final
# api compatible object
alias_map = build_alias_map(data)

# Filter out keys we don't want in the jsonschema we pass to
# datamodel-code-generator.
data = process_keys(
    data,
    {
        # uniqueItems is supported by pydantic but there is a bug
        # we are hitting.
        # https://github.com/samuelcolvin/pydantic/issues/3957
        "uniqueItems": MappingOperator.DELETE
    },
)

# datamodel-code-generator doesn't support specifying context
# directory when resolving $refs. Therefor we have to effectively
# `cd` into the API_ROOT first.
os.chdir(API_ROOT)

print("Generating pulsar model...")

# Run actual model generation using datamodel-code-generator
generate(
    json.dumps(data),
    input_file_type=InputFileType.JsonSchema,
    target_python_version=PythonVersion.PY_39,
    output=pathlib.Path(OUT_FILE),
    aliases=alias_map,
    validation=True,
    reuse_model=True,
    use_subclass_enum=True,
    allow_population_by_field_name=True,
    field_extra_keys=set({"uri", "method", "immutable"}),
    use_double_quotes=True,
)

print(f"Successfully generated {OUT_FILE}")
