import kopf
import models
from models import NeuronStatus, status_handler
from api import API, Tenant, Namespace, Topic, APIException
from .common import CLUSTER_ANNOTATION, CommonConditionType
from enum import Enum

ERROR_DELAY = 5


# Available condition types for NeuronTopic
class TopicConditionType(str, Enum):
    ConnectionOK = "ConnectionOK"
    TenantReady = "TenantReady"
    NamespaceReady = "NamespaceReady"
    TopicInSync = "TopicInSync"


# Available phases for NeuronTopic
class TopicPhase(str, Enum):
    Pending = "Pending"
    Ready = "Ready"
    Failed = "Failed"


# Available reasons for NeuronTopic condition
class TopicReason(str, Enum):
    TenantNotFound = "Tenant not found in Pulsar cluster"
    NamespaceNotFound = "Namespace not found in Pulsar cluster"
    TopicLevelPoliciesDisabled = (
        "Topic level policies are disabled and policies are defined for topic"
    )
    DeleteFailed = "Delete failed"


########################
## Main Topic Handler ##
########################
def cluster_check(value: str, memo: kopf.Memo, **_):
    return value == memo.get("cluster_name")


@kopf.on.update("neuron.isf", "neurontopics", retries=3, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.resume("neuron.isf", "neurontopics", retries=3, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.timer("neuron.isf", "neurontopics", retries=3, initial_delay=60, interval=600, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def topic_handler(
    status: NeuronStatus,
    memo: kopf.Memo,
    meta: dict,
    spec: dict,
    **_,
):
    # At this point we can fix ClusterTargetOK condition
    status.set_condition(CommonConditionType.ClusterTargetOK, True)

    # Mapping spec to a Python native model class
    model = models.TopicSpec(**spec)

    # Get Pulsar client from memo
    pulsar_client = memo.get("pulsar_client")
    api: API
    if pulsar_client and type(pulsar_client) == API:
        api = pulsar_client
    else:
        raise kopf.PermanentError("No pulsar client available")

    ############################
    ## Check Tenant in Pulsar ##
    ############################
    tenant = Tenant(name=model.tenant, **{})
    if not api.tenant.exists(tenant):
        status.set_condition(
            TopicConditionType.TenantReady,
            False,
            reason=TopicReason.TenantNotFound.name,
            message=TopicReason.TenantNotFound,
        )
        status.set_phase(TopicPhase.Failed)
        raise kopf.TemporaryError(
            f"Tenant '{model.tenant}' not found in Pulsar", delay=ERROR_DELAY
        )
    else:
        status.set_condition(TopicConditionType.TenantReady, True)

    ###############################
    ## Check Namespace in Pulsar ##
    ###############################
    ns = Namespace(name=model.namespace, tenant=model.tenant, **{})
    if not api.namespace.exists(ns):
        status.set_condition(
            TopicConditionType.NamespaceReady,
            False,
            reason=TopicReason.NamespaceNotFound.name,
            message=TopicReason.NamespaceNotFound,
        )
        status.set_phase(TopicPhase.Failed)
        raise kopf.TemporaryError(
            f"Namespace '{model.namespace}' not found in Pulsar", delay=ERROR_DELAY
        )
    else:
        status.set_condition(TopicConditionType.NamespaceReady, True)

    ############################
    ## Handle Topic in Pulsar ##
    ############################
    # Create a Topic instance needed by the API wrapper
    topic = Topic.from_spec(model)

    # If topic level policies are not enabled but policies are
    # specified, we should fail.
    if not api.topic.topic_level_policies_enabled() and model.policies != None:
        status.set_condition(
            TopicConditionType.TopicInSync,
            False,
            reason=TopicReason.TopicLevelPoliciesDisabled.name,
            message=TopicReason.TopicLevelPoliciesDisabled,
        )
        status.set_phase(TopicPhase.Failed)
        raise kopf.PermanentError(TopicReason.TopicLevelPoliciesDisabled)

    # Topic doesn't already exist
    if not api.topic.exists(topic):
        try:
            api.topic.create(topic)
        except APIException as e:
            status.set_condition(TopicConditionType.TopicInSync, False, message=str(e))
            status.set_phase(TopicPhase.Pending)
            raise kopf.TemporaryError(f"Unable to create topic: {e}", delay=ERROR_DELAY)

    # Sync permissions
    try:
        api.topic.sync_permissions(topic)
    except APIException as e:
        status.set_condition(TopicConditionType.TopicInSync, False, message=str(e))
        status.set_phase(TopicPhase.Pending)
        raise kopf.TemporaryError(
            f"Unable to set topic permissions: {e}", delay=ERROR_DELAY
        )

    # Check if topic level policies are enabled and update if so
    if api.topic.topic_level_policies_enabled():
        try:
            api.topic.update(topic)
        except APIException as e:
            status.set_condition(TopicConditionType.TopicInSync, False, message=str(e))
            status.set_phase(TopicPhase.Pending)
            raise kopf.TemporaryError(
                f"Unable to update topic level policies: {e}", delay=ERROR_DELAY
            )

    # If we reached this far everything should be fine
    status.set_condition(TopicConditionType.TopicInSync, True)

    #######################
    ## Set correct phase ##
    #######################
    if status.conditions_ok():
        status.set_phase(TopicPhase.Ready)
        status.observedGeneration = meta.get("generation")


####################
## Delete Handler ##
####################
@kopf.on.delete("neuron.isf", "neurontopics", annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def delete(
    status: NeuronStatus, memo: kopf.Memo, body: kopf.Body, logger: kopf.Logger, **_
):
    model = models.TopicSpec(**body.spec)
    if model.lifecyclePolicy == models.LifecyclePolicy.CleanUpAfterDeletion:
        # Get Pulsar client from memo
        pulsar_client = memo.get("pulsar_client")
        api: API
        if pulsar_client and type(pulsar_client) == API:
            api = pulsar_client
        else:
            raise kopf.PermanentError("No pulsar client available")
        topic = Topic.from_spec(model)

        try:
            if api.topic.exists(topic):
                try:
                    api.topic.delete(topic)
                except Exception as e:
                    status.set_condition(
                        TopicConditionType.TopicInSync,
                        False,
                        reason=TopicReason.DeleteFailed.name,
                        message=str(e),
                    )
                    status.set_phase(TopicPhase.Pending)
                    raise kopf.TemporaryError(f"Unable to delete topic: {e}", delay=10)
        except APIException as e:
            logger.warn(f"Unable to check topic existence: {e.message}")
            logger.warn("Releasing resource anyway.")


###########
## Index ##
###########
# This index is needed by the schema handler to be able to lookup some settings of
# the topic it wants in order to correctly build the API url (e.g. persistence and
# partition count).
@kopf.index("neuron.isf", "neurontopics", annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
def topic_idx(spec: dict, **_):
    model = models.TopicSpec(**spec)
    selector = (model.tenant, model.namespace, model.topic)
    return {selector: model}
