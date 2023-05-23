from models import (
    PulsarTenantSettings,
    PulsarNamespacePolicies,
    PulsarTopicPolicies,
    SchemaCompatibilityStrategy,
)

#####################
## Tenant settings ##
#####################
def test_tenant_api_dict():
    ts = {
        "adminRoles": ["admin"],
        "allowedClusters": ["dev01"],
    }
    tenant_settings = PulsarTenantSettings(**ts)
    assert tenant_settings.api_dict() == ts


########################
## Namespace policies ##
########################
def test_namespace_policies_api_dict():
    np = {
        "replicationClusters": ["dev01"],
        "schemaCompatibilityStrategy": "FORWARD_TRANSITIVE",
        "deduplicationEnabled": True,
        "schemaValidationEnforced": True,
        "properties": {"property1": "hello"},
    }
    expected = {
        "replication_clusters": ["dev01"],
        "schema_compatibility_strategy": SchemaCompatibilityStrategy.FORWARD_TRANSITIVE,
        "deduplicationEnabled": True,
        "schema_validation_enforced": True,
        "properties": {"property1": "hello"},
    }
    namespace_policies = PulsarNamespacePolicies(**np)

    assert namespace_policies.api_dict() == expected
