import json
from models import SchemaSpec
from .api import BaseAPI, APIException, APIRequestType
from typing import Optional, Dict, Any
from dataclasses import dataclass


class SchemaNotFoundException(Exception):
    pass


class IncompatibleSchemaException(Exception):
    pass


class ParsingException(Exception):
    pass


def no_none(d: Dict) -> Dict:
    ret = {}
    for k in d.keys():
        if d.get(k) != None:
            ret[k] = d.get(k)
    return ret


# Dataclass for a Pulsar schema. It supports parsing from a CRD .spec
# and from API.
# It has a dict() method that outputs the schema in a format the
# Pulsar API understands.
@dataclass
class Schema:
    type: str
    schema: Dict[str, Any]
    version: Optional[int] = None
    timestamp: Optional[int] = None
    properties: Optional[dict] = None

    tenant: Optional[str] = None
    namespace: Optional[str] = None
    topic: Optional[str] = None

    @classmethod
    def from_spec(cls, spec: SchemaSpec):
        return cls(
            tenant=spec.tenant,
            namespace=spec.namespace,
            topic=spec.topic,
            type=spec.type or "AVRO",
            schema=spec.schema_.dict(exclude_none=True),
            properties=spec.properties,
        )

    @classmethod
    def from_api(cls, data: str, **kwargs):
        schema = json.loads(data)
        return cls(**dict(kwargs, schema=schema))

    def dict(self) -> Dict[str, str]:
        # API expects the nested schema field to be a JSON string instead
        # of a nested object
        return no_none(
            {
                "type": self.type,
                "schema": json.dumps(self.schema),
                "properties": self.properties,
            }
        )


class SchemaAPI(BaseAPI):
    __base_url__: str

    def get(self, schema: Schema) -> Schema:
        url = "{base_url}/schemas/{tenant}/{namespace}/{topic}/schema".format(
            base_url=self.__base_url__,
            tenant=schema.tenant,
            namespace=schema.namespace,
            topic=schema.topic,
        )

        r = self._get(url)

        if r.status_code == 200:
            try:
                data = r.json()
                return Schema.from_api(**data)
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            try:
                self._handle_error(r)
            except APIException as e:
                if e.status_code == 404:
                    raise SchemaNotFoundException()
                raise e

    def exists(self, schema: Schema) -> bool:
        try:
            s = self.get(schema)
            return s != None
        except SchemaNotFoundException:
            return False

    def update(self, schema: Schema) -> Schema:
        url = "{base_url}/schemas/{tenant}/{namespace}/{topic}/schema".format(
            base_url=self.__base_url__,
            tenant=schema.tenant,
            namespace=schema.namespace,
            topic=schema.topic,
        )

        r = self._post(url, json=schema.dict())

        # API docs say 200 is success but I've only ever seen
        # 202. Let's catch 200-202 just in case as success ;)
        if 200 <= r.status_code <= 202:
            try:
                data = r.json()
                # I'm expexting `{"version": {"version": 1}}` back
                if (
                    isinstance(data, dict)
                    and isinstance(data.get("version"), dict)
                    and "version" in data["version"]
                ):
                    schema.version = data["version"]["version"]

                return schema
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            try:
                self._handle_error(r)
            except APIException as e:
                if e.status_code == 409:  # 409 Conflict
                    raise IncompatibleSchemaException("Schema is incompatible")
                raise e

    def delete(self, schema: Schema) -> None:
        url = "{base_url}/schemas/{tenant}/{namespace}/{topic}/schema".format(
            base_url=self.__base_url__,
            tenant=schema.tenant,
            namespace=schema.namespace,
            topic=schema.topic,
        )

        r = self._delete(url, json=schema.dict())

        if r.status_code != 200:
            self._handle_error(r)
