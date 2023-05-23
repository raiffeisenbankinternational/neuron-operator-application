from models import TopicSpec, RolePermissionEnum
from models.pulsar import APIValue
from ..topic_api import TopicAPI, Topic
from datetime import datetime
import requests_mock


def test_topic_init():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": False,
            "partitions": 16,
            "deduplicationEnabled": True,
            "retentionPolicies": {
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
            "inactiveTopicPolicies": {
                "deleteWhileInactive": False,
                "maxInactiveDurationSeconds": 60,
            },
        },
    )

    assert topic.name == "sample"
    assert topic.tenant == "sample-tenant"
    assert topic.namespace == "sample-namespace"
    assert topic.persistent == False
    assert topic.partitions == 16
    assert topic.deduplicationEnabled == True
    assert topic.retentionPolicies != None
    assert topic.retentionPolicies.retentionTimeInMinutes == 3600
    assert topic.retentionPolicies.retentionSizeInMB == 1024
    assert topic.inactiveTopicPolicies != None
    assert topic.inactiveTopicPolicies.deleteWhileInactive == False
    assert topic.inactiveTopicPolicies.maxInactiveDurationSeconds == 60
    assert topic.inactiveTopicPolicies.inactiveTopicDeleteMode == None


def test_full_name_persistent():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": True,
        },
    )
    assert topic.full_name == "persistent://sample-tenant/sample-namespace/sample"


def test_full_name_non_persistent():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": False,
        },
    )
    assert topic.full_name == "non-persistent://sample-tenant/sample-namespace/sample"


def test_api_dict():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "deduplicationEnabled": True,
            "retentionPolicies": {
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
            "inactiveTopicPolicies": {
                "deleteWhileInactive": False,
                "maxInactiveDurationSeconds": 60,
            },
        },
    )
    expected = {
        "deduplicationEnabled": True,
        "retention_policies": {
            "retentionTimeInMinutes": 3600,
            "retentionSizeInMB": 1024,
        },
        "inactive_topic_policies": {
            "deleteWhileInactive": False,
            "maxInactiveDurationSeconds": 60,
        },
    }
    assert topic.api_dict() == expected


def test_api_uris():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "deduplicationEnabled": True,
            "retentionPolicies": {
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
            "inactiveTopicPolicies": {
                "deleteWhileInactive": False,
                "maxInactiveDurationSeconds": 60,
            },
        },
    )
    expected = {
        "deduplicationEnabled": APIValue(
            uri="/deduplicationEnabled",
            method="POST",
            value=True,
        ),
        "retention_policies": APIValue(
            uri="/retention",
            method="POST",
            value={
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
        ),
        "inactive_topic_policies": APIValue(
            uri="/inactiveTopicPolicies",
            method="POST",
            value={
                "maxInactiveDurationSeconds": 60,
                "deleteWhileInactive": False,
            },
        ),
    }
    assert topic.api_uris() == expected


def test_from_spec():
    topic = Topic.from_spec(
        TopicSpec(
            **{
                "tenant": "sample-tenant",
                "namespace": "sample-namespace",
                "topic": "sample",
                "policies": {
                    "deduplicationEnabled": True,
                    "retentionPolicies": {
                        "retentionTimeInMinutes": 3600,
                        "retentionSizeInMB": 1024,
                    },
                },
            }
        )
    )

    assert topic.name == "sample"
    assert topic.namespace == "sample-namespace"
    assert topic.tenant == "sample-tenant"
    assert topic.deduplicationEnabled == True
    assert topic.retentionPolicies.retentionTimeInMinutes == 3600
    assert topic.retentionPolicies.retentionSizeInMB == 1024


def test_topic_permissions():
    topic = Topic(
        name="sample",
        tenant="sample-tenant",
        namespace="sample-namespace",
        persistent=True,
        role_permissions={
            "MY-ROLE": [RolePermissionEnum.consume, RolePermissionEnum.produce]
        },
        **{},
    )

    assert topic.permissions == {"MY-ROLE": ["consume", "produce"]}


##################################
## CREATE NON-PARTITIONED TOPIC ##
##################################
def handle_non_partitioned(req, ctx):
    if req.text != None:
        ctx.status_code = 412
    else:
        ctx.status_code = 201
    return req.text


def test_create_non_partitioned():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": True,
            "deduplicationEnabled": True,
            "retentionPolicies": {
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
            "inactiveTopicPolicies": {
                "deleteWhileInactive": False,
                "maxInactiveDurationSeconds": 60,
            },
        },
    )
    api = TopicAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.put(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample",
            text=handle_non_partitioned,
        )
        api.create(topic)


##############################
## CREATE PARTITIONED TOPIC ##
##############################
def handle_partitioned(req, ctx):
    if req.text == None:
        ctx.status_code = 412
    else:
        ctx.status_code = 201 if req.json() == 16 else 412
    return req.text


def test_create_partitioned():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": True,
            "partitions": 16,
            "deduplicationEnabled": True,
            "retentionPolicies": {
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
            "inactiveTopicPolicies": {
                "deleteWhileInactive": False,
                "maxInactiveDurationSeconds": 60,
            },
        },
    )
    api = TopicAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.put(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/partitions",
            text=handle_partitioned,
        )
        api.create(topic)


############
## EXISTS ##
############
def test_exists_success():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": True,
            "deduplicationEnabled": True,
            "retentionPolicies": {
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
            "inactiveTopicPolicies": {
                "deleteWhileInactive": False,
                "maxInactiveDurationSeconds": 60,
            },
        },
    )
    api = TopicAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace",
            json=[
                "persistent://sample-tenant/sample-namespace/sample",
                "persistent://sample-tenant/sample-namespace/another-topic",
            ],
        )
        exists = api.exists(topic)
        assert exists == True


def test_exists_failure():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": True,
            "deduplicationEnabled": True,
            "retentionPolicies": {
                "retentionTimeInMinutes": 3600,
                "retentionSizeInMB": 1024,
            },
            "inactiveTopicPolicies": {
                "deleteWhileInactive": False,
                "maxInactiveDurationSeconds": 60,
            },
        },
    )
    api = TopicAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace",
            json=[
                "persistent://sample-tenant/sample-namespace/not-sample",
                "persistent://sample-tenant/sample-namespace/another-topic",
            ],
        )
        exists = api.exists(topic)
        assert exists == False


##########################
## TOPIC LEVEL POLICIES ##
##########################
def test_topic_level_policies_enabled():
    api = TopicAPI("http://localhost:8090/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8090/admin/v2/brokers/configuration/runtime",
            json={"topicLevelPoliciesEnabled": "true"},
        )
        assert api.topic_level_policies_enabled() == True


def test_topic_level_policies_disabled():
    api = TopicAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/brokers/configuration/runtime",
            json={"topicLevelPoliciesEnabled": "false"},
        )
        assert api.topic_level_policies_enabled() == False


def test_topic_level_policies_is_cached():
    api = TopicAPI("http://localhost:8080/admin/v2")

    # Prefilling the cache
    api.__config__ = {"topicLevelPoliciesEnabled": "true"}
    api.__config_fetched__ = datetime.now()

    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/brokers/configuration/runtime",
            json={"topicLevelPoliciesEnabled": "false"},
        )
        assert api.topic_level_policies_enabled() == True
        assert m.called == False


#################
## PERMISSIONS ##
#################
def test_get_permissions():
    topic = Topic(
        name="sample",
        **{
            "tenant": "sample-tenant",
            "namespace": "sample-namespace",
            "persistent": True,
        },
    )
    api = TopicAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample-namespace/permissions",
            text='{"MY-ROLE":["consume","produce"],"MY-ROLE2":["consume"]}',
        )
        m.get(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions",
            text='{"MY-ROLE":["consume","produce"],"MY-ROLE2":["produce"],"MY-ROLE3":["consume","produce"]}',
        )

        assert api.permissions(topic) == {"MY-ROLE2":["produce"],"MY-ROLE3":["consume","produce"]}


def test_sync_permissions():
    # Wanted state
    ns = Topic(
        name="sample",
        tenant="sample-tenant",
        namespace="sample-namespace",
        persistent=True,
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

    api = TopicAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        # Get current state from API
        m.get(
            "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample-namespace/permissions",
            text='{"MY-ROLE":["consume","produce"],"MY-ROLE2":["consume"]}',
        )        
        m.get(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions",
            json=res,
        )
        # Update MY-PRODUCER
        m.post(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions/MY-PRODUCER",
            json=ns.permissions["MY-PRODUCER"],
        )
        # Update MY-CONSUMER
        m.post(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions/MY-CONSUMER",
            json=ns.permissions["MY-CONSUMER"],
        )
        # Delete OLD-ROLE
        m.delete(
            "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions/OLD-ROLE"
        )

        api.sync_permissions(ns)

        history = m.request_history

        assert len(history) == 5
        assert history[0].method == "GET"
        assert (
            history[0].url
            == "http://localhost:8080/admin/v2/namespaces/sample-tenant/sample-namespace/permissions"
        )
        assert history[1].method == "GET"
        assert (
            history[1].url
            == "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions"
        )
        assert history[2].method == "POST"
        assert (
            history[2].url
            == "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions/MY-PRODUCER"
        )
        assert history[3].method == "POST"
        assert (
            history[3].url
            == "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions/MY-CONSUMER"
        )
        assert history[4].method == "DELETE"
        assert (
            history[4].url
            == "http://localhost:8080/admin/v2/persistent/sample-tenant/sample-namespace/sample/permissions/OLD-ROLE"
        )
