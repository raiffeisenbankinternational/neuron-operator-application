from models import SchemaSpec
from ..schema_api import (
    SchemaAPI,
    Schema,
    SchemaNotFoundException,
    IncompatibleSchemaException,
)
import pytest
import requests_mock
import json

test_spec = {
    "tenant": "sample-tenant",
    "namespace": "sample-namespace",
    "topic": "sample-topic",
    "type": "AVRO",
    "schema": {
        "name": "MySchema",
        "type": "record",
        "fields": [
            {"name": "MandatoryField", "type": "string"},
            {"name": "OptionalField", "type": ["null", "string"]},
        ],
    },
    "properties": {"test": 1},
}


def test_from_spec():
    schema = Schema.from_spec(SchemaSpec(**test_spec))

    assert schema.tenant == "sample-tenant"
    assert schema.namespace == "sample-namespace"
    assert schema.topic == "sample-topic"
    assert schema.type == "AVRO"
    assert schema.schema == {
        "name": "MySchema",
        "type": "record",
        "fields": [
            {"name": "MandatoryField", "type": "string"},
            {"name": "OptionalField", "type": ["null", "string"]},
        ],
    }
    assert schema.properties == {"test": 1}


def test_api_dict():
    expected = {
        "type": "AVRO",
        "schema": json.dumps(
            {
                "name": "MySchema",
                "type": "record",
                "fields": [
                    {
                        "name": "MandatoryField",
                        "type": "string",
                    },
                    {
                        "name": "OptionalField",
                        "type": ["null", "string"],
                    },
                ],
            }
        ),
        "properties": {"test": 1},
    }
    schema = Schema(**test_spec)
    assert schema.dict() == expected


#########
## GET ##
#########
def test_get():
    ret = {
        "version": 5,
        "type": "AVRO",
        "timestamp": 0,
        "data": json.dumps(
            {
                "name": "MySchema",
                "type": "record",
                "fields": [
                    {
                        "name": "MandatoryField",
                        "type": "string",
                    },
                    {
                        "name": "OptionalField",
                        "type": ["null", "string"],
                    },
                ],
            }
        ),
        "properties": {},
    }
    api = SchemaAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/schemas/sample-tenant/sample-namespace/sample-topic/schema",
            status_code=200,
            json=ret,
        )
        schema = api.get(Schema.from_spec(SchemaSpec(**test_spec)))
        assert schema.type == "AVRO"
        assert schema.schema == json.loads(ret["data"])


def test_get_not_found():
    api = SchemaAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/schemas/sample-tenant/sample-namespace/sample-topic/schema",
            status_code=404,
        )
        with pytest.raises(SchemaNotFoundException):
            _ = api.get(Schema.from_spec(SchemaSpec(**test_spec)))


############
## EXISTS ##
############
def test_exists():
    ret = {
        "version": 5,
        "type": "AVRO",
        "timestamp": 0,
        "data": json.dumps(
            {
                "name": "MySchema",
                "type": "record",
                "fields": [
                    {
                        "name": "MandatoryField",
                        "type": "string",
                    },
                    {
                        "name": "OptionalField",
                        "type": ["null", "string"],
                    },
                ],
            }
        ),
        "properties": {},
    }
    api = SchemaAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/schemas/sample-tenant/sample-namespace/sample-topic/schema",
            status_code=200,
            json=ret,
        )
        assert api.exists(Schema.from_spec(SchemaSpec(**test_spec)))


def test_not_exists():
    api = SchemaAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/schemas/sample-tenant/sample-namespace/sample-topic/schema",
            status_code=404,
        )
        assert not api.exists(Schema.from_spec(SchemaSpec(**test_spec)))


############
## UPDATE ##
############
def test_update():
    ret = {"version": {"version": 4}}
    schema = Schema.from_spec(SchemaSpec(**test_spec))
    api = SchemaAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.post(
            "http://localhost:8080/admin/v2/schemas/sample-tenant/sample-namespace/sample-topic/schema",
            status_code=202,
            json=ret,
        )
        sch = api.update(schema)
        assert sch.version == 4


def test_update_incompatible_schema():
    schema = Schema.from_spec(SchemaSpec(**test_spec))
    api = SchemaAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.post(
            "http://localhost:8080/admin/v2/schemas/sample-tenant/sample-namespace/sample-topic/schema",
            status_code=409,
        )
        with pytest.raises(IncompatibleSchemaException):
            _ = api.update(schema)
