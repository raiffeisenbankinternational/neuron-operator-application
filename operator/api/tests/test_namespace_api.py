from models import NamespaceSpec, SchemaCompatibilityStrategy, RolePermissionEnum
from models.pulsar import APIValue
from ..namespace_api import NamespaceAPI, Namespace
import requests_mock
import json


def test_parse():
    ns = Namespace(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "schemaValidationEnforced": True,
            "schemaCompatibilityStrategy": "FORWARD_TRANSITIVE",
            "isAllowAutoUpdateSchema": False,
            "maxConsumersPerTopic": 10,
            "autoTopicCreationOverride": {"allowAutoTopicCreation": False},
        },
    )

    assert ns.name == "sample"
    assert ns.tenant == "sample-tenant"
    assert ns.schemaValidationEnforced == True
    assert (
        ns.schemaCompatibilityStrategy == SchemaCompatibilityStrategy.FORWARD_TRANSITIVE
    )
    assert ns.isAllowAutoUpdateSchema == False
    assert ns.maxConsumersPerTopic == 10
    assert ns.autoTopicCreationOverride != None
    assert ns.autoTopicCreationOverride.allowAutoTopicCreation == False


def test_api_dict():
    ns = Namespace(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "schemaValidationEnforced": True,
            "schemaCompatibilityStrategy": "FORWARD_TRANSITIVE",
            "isAllowAutoUpdateSchema": False,
            "maxConsumersPerTopic": 10,
            "autoTopicCreationOverride": {"allowAutoTopicCreation": False},
        },
    )
    expected = {
        "schema_validation_enforced": True,
        "schema_compatibility_strategy": SchemaCompatibilityStrategy.FORWARD_TRANSITIVE,
        "is_allow_auto_update_schema": False,
        "max_consumers_per_topic": 10,
        "autoTopicCreationOverride": {"allowAutoTopicCreation": False},
    }

    assert ns.api_dict() == expected


def test_api_uris():
    ns = Namespace(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "schemaValidationEnforced": True,
            "schemaCompatibilityStrategy": "FORWARD_TRANSITIVE",
            "isAllowAutoUpdateSchema": False,
            "maxConsumersPerTopic": 10,
            "autoTopicCreationOverride": {"allowAutoTopicCreation": False},
        },
    )
    expected = {
        "schema_validation_enforced": APIValue(
            uri="/schemaValidationEnforced",
            method="POST",
            value=True,
        ),
        "schema_compatibility_strategy": APIValue(
            uri="/schemaCompatibilityStrategy",
            method="PUT",
            value="FORWARD_TRANSITIVE",
        ),
        "is_allow_auto_update_schema": APIValue(
            uri="/isAllowAutoUpdateSchema",
            method="POST",
            value=False,
        ),
        "max_consumers_per_topic": APIValue(
            uri="/maxConsumersPerTopic",
            method="POST",
            value=10,
        ),
        "autoTopicCreationOverride": APIValue(
            uri="/autoTopicCreation",
            method="POST",
            value={"allowAutoTopicCreation": False},
        ),
    }

    assert ns.api_uris() == expected


def test_from_spec():
    namespace = Namespace.from_spec(
        NamespaceSpec(
            **{
                "tenant": "sample-tenant",
                "namespace": "sample",
                "policies": {
                    "schemaValidationEnforced": True,
                    "schemaCompatibilityStrategy": "FORWARD_TRANSITIVE",
                    "isAllowAutoUpdateSchema": False,
                    "maxConsumersPerTopic": 10,
                },
            }
        )
    )

    assert namespace.name == "sample"
    assert namespace.tenant == "sample-tenant"
    assert namespace.schemaValidationEnforced == True
    assert (
        namespace.schemaCompatibilityStrategy
        == SchemaCompatibilityStrategy.FORWARD_TRANSITIVE
    )
    assert namespace.isAllowAutoUpdateSchema == False
    assert namespace.maxConsumersPerTopic == 10


def test_namespace_permissions():
    ns = Namespace(
        name="sample",
        tenant="sample-tenant",
        role_permissions={
            "MY-ROLE": [RolePermissionEnum.consume, RolePermissionEnum.produce]
        },
        **{},
    )

    assert ns.permissions == {"MY-ROLE": ["consume", "produce"]}


#########
## GET ##
#########
def test_get():
    def handler(_, ctx):
        ctx.status_code = 200
        return json.dumps(
            {
                "schema_validation_enforced": True,
                "schema_compatibility_strategy": "FORWARD_TRANSITIVE",
                "is_allow_auto_update_schema": False,
                "max_consumers_per_topic": 10,
                "autoTopicCreationOverride": {"allowAutoTopicCreation": False},
            }
        )

    ns = Namespace(name="sample", tenant="sample-tenant", **{})
    api = NamespaceAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample",
            text=handler,
        )

        namespace = api.get(ns)

        assert namespace.name == "sample"
        assert namespace.tenant == "sample-tenant"
        assert namespace.schemaValidationEnforced == True
        assert (
            namespace.schemaCompatibilityStrategy
            == SchemaCompatibilityStrategy.FORWARD_TRANSITIVE
        )
        assert namespace.isAllowAutoUpdateSchema == False
        assert namespace.maxConsumersPerTopic == 10
        assert namespace.autoTopicCreationOverride != None
        assert namespace.autoTopicCreationOverride.allowAutoTopicCreation == False


############
## CREATE ##
############
def test_create():
    ret = {
        "bundles": {
            "boundaries": [
                "0x00000000",
                "0x40000000",
                "0x80000000",
                "0xc0000000",
                "0xffffffff",
            ],
            "numBundles": 4,
        },
        "schema_validation_enforced": True,
        "schema_compatibility_strategy": "UNDEFINED",
        "is_allow_auto_update_schema": False,
        "encryption_required": False,
    }
    expected_ret = dict(
        ret, schema_compatibility_strategy=SchemaCompatibilityStrategy.UNDEFINED
    )

    def handler(_, ctx):
        ctx.status_code = 200
        return json.dumps(ret)

    ns = Namespace(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "schemaValidationEnforced": True,
            "isAllowAutoUpdateSchema": False,
        },
    )
    expected = {
        "schema_validation_enforced": True,
        "is_allow_auto_update_schema": False,
    }
    api = NamespaceAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.put(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample",
            json=expected,
            status_code=204,
        )
        m.get(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample",
            text=handler,
        )
        namespace = api.create(ns)

        assert namespace.api_dict() == expected_ret
        assert namespace.schemaValidationEnforced == ns.schemaValidationEnforced
        assert namespace.isAllowAutoUpdateSchema == ns.isAllowAutoUpdateSchema


############
## UPDATE ##
############
def test_update():
    ret = {
        "bundles": {
            "boundaries": [
                "0x00000000",
                "0x40000000",
                "0x80000000",
                "0xc0000000",
                "0xffffffff",
            ],
            "numBundles": 4,
        },
        "schema_validation_enforced": True,
        "schema_compatibility_strategy": "FORWARD_TRANSITIVE",
        "is_allow_auto_update_schema": False,
        "encryption_required": False,
    }
    expected_ret = dict(
        ret,
        schema_compatibility_strategy=SchemaCompatibilityStrategy.FORWARD_TRANSITIVE,
    )

    def handler(_, ctx):
        ctx.status_code = 200
        return json.dumps(ret)

    ns = Namespace(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "schemaValidationEnforced": True,
            "schemaCompatibilityStrategy": SchemaCompatibilityStrategy.FORWARD_TRANSITIVE,
            "isAllowAutoUpdateSchema": False,
        },
    )
    api = NamespaceAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.post(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/schemaValidationEnforced",
            json=True,
            status_code=204,
        )
        m.put(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/schemaCompatibilityStrategy",
            json="FORWARD_TRANSITIVE",
            status_code=204,
        )
        m.post(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/isAllowAutoUpdateSchema",
            json=False,
            status_code=204,
        )
        m.get(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample",
            text=handler,
        )
        namespace = api.update(ns)

        assert namespace.api_dict() == expected_ret
        assert namespace.schemaValidationEnforced == ns.schemaValidationEnforced
        assert namespace.schemaCompatibilityStrategy == ns.schemaCompatibilityStrategy
        assert namespace.isAllowAutoUpdateSchema == ns.isAllowAutoUpdateSchema


#################
## PERMISSIONS ##
#################
def test_get_permissions():
    ns = Namespace(
        name="sample",
        tenant="sample-tenant",
        **{},
    )
    api = NamespaceAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions",
            text='{"MY-ROLE":["consume","produce"]}',
        )

        assert api.permissions(ns) == {"MY-ROLE": ["consume", "produce"]}


def test_sync_permissions():
    # Wanted state
    ns = Namespace(
        name="sample",
        tenant="sample-tenant",
        role_permissions={
            "MY-PRODUCER": [RolePermissionEnum.produce],
            "MY-CONSUMER": [RolePermissionEnum.consume],
        },
        **{},
    )
    # Reality
    res = {
        "MY-CONSUMER": [RolePermissionEnum.consume],
        "OLD-ROLE": [
            RolePermissionEnum.consume,
            RolePermissionEnum.produce,
            RolePermissionEnum.functions,
        ],
    }

    api = NamespaceAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        # Get current state from API
        m.get(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions",
            json=res,
        )
        # Update MY-PRODUCER
        m.post(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions/MY-PRODUCER",
            json=ns.permissions["MY-PRODUCER"],
        )
        # Update MY-CONSUMER
        m.post(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions/MY-CONSUMER",
            json=ns.permissions["MY-CONSUMER"],
        )
        # Delete OLD-ROLE
        m.delete(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions/OLD-ROLE"
        )

        api.sync_permissions(ns)

        history = m.request_history

        assert len(history) == 4
        assert history[0].method == "GET"
        assert (
            history[0].url
            == "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions"
        )
        assert history[1].method == "POST"
        assert (
            history[1].url
            == "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions/MY-PRODUCER"
        )
        assert history[2].method == "POST"
        assert (
            history[2].url
            == "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions/MY-CONSUMER"
        )
        assert history[3].method == "DELETE"
        assert (
            history[3].url
            == "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample/permissions/OLD-ROLE"
        )
