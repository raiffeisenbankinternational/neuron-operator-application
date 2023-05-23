import kopf
import models
from models import NeuronStatus, status_handler
from api import API, Tenant, Namespace, Topic, Schema, APIException
from api.schema_api import IncompatibleSchemaException, ParsingException
from .common import CLUSTER_ANNOTATION, CommonConditionType
from enum import Enum


ERROR_DELAY = 5


# Available condition types for NeuronSchema
class SchemaConditionType(str, Enum):
    ConnectionOK = "ConnectionOK"
    TenantReady = "TenantReady"
    NamespaceReady = "NamespaceReady"
    TopicReady = "TopicReady"
    SchemaInSync = "SchemaInSync"


# Available phases for NeuronSchema
class SchemaPhase(str, Enum):
    Pending = "Pending"
    Ready = "Ready"
    Failed = "Failed"


# Available reasons for NeuronSchema condition
class SchemaReason(str, Enum):
    TenantNotFound = "Tenant not found in Pulsar cluster"
    NamespaceNotFound = "Namespace not found in Pulsar cluster"
    TopicNotFound = "Topic not found in Pulsar cluster"
    IncompatibleSchema = "Incompatible schema"
    ResponseParsingError = "Error parsing response from Pulsar cluster"
    DeleteFailed = "Delete failed"
    UnknownError = "Unknown error"


#########################
## Main Schema Handler ##
#########################
def cluster_check(value: str, memo: kopf.Memo, **_):
    return value == memo.get("cluster_name")


@kopf.on.update("neuron.isf", "neuronschemas", retries=3, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.resume("neuron.isf", "neuronschemas", retries=3, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.timer("neuron.isf", "neuronschemas", retries=3, initial_delay=60, interval=600, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def schema_handler(
    status: NeuronStatus,
    memo: kopf.Memo,
    body: kopf.Body,
    topic_idx: kopf.Index,
    **_,
):
    # At this point we can fix ClusterTargetOK condition
    status.set_condition(CommonConditionType.ClusterTargetOK, True)

    # Mapping spec to a Python native model class
    model = models.SchemaSpec(**body.spec)

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
            SchemaConditionType.TenantReady,
            False,
            reason=SchemaReason.TenantNotFound.name,
            message=SchemaReason.TenantNotFound,
        )
        status.set_phase(SchemaPhase.Failed)
        raise kopf.TemporaryError(
            f"Tenant '{model.tenant}' not found in Pulsar", delay=ERROR_DELAY
        )
    else:
        status.set_condition(SchemaConditionType.TenantReady, True)

    ###############################
    ## Check Namespace in Pulsar ##
    ###############################
    ns = Namespace(name=model.namespace, tenant=model.tenant, **{})
    if not api.namespace.exists(ns):
        status.set_condition(
            SchemaConditionType.NamespaceReady,
            False,
            reason=SchemaReason.NamespaceNotFound.name,
            message=SchemaReason.NamespaceNotFound,
        )
        status.set_phase(SchemaPhase.Failed)
        raise kopf.TemporaryError(
            f"Namespace '{model.namespace}' not found in Pulsar", delay=ERROR_DELAY
        )
    else:
        status.set_condition(SchemaConditionType.NamespaceReady, True)

    ###########################
    ## Check Topic in Pulsar ##
    ###########################
    selector = (model.tenant, model.namespace, model.topic)
    topic: Topic
    if selector in topic_idx:
        topic_spec, *_ = topic_idx[selector]
        topic = Topic.from_spec(topic_spec)
    else:
        status.set_condition(
            SchemaConditionType.TopicReady,
            False,
            reason=SchemaReason.TopicNotFound.name,
            message=SchemaReason.TopicNotFound,
        )
        status.set_phase(SchemaPhase.Failed)
        raise kopf.TemporaryError(
            f"Topic '{model.tenant}/{model.namespace}/{model.topic}' not found in cluster",
            delay=ERROR_DELAY,
        )

    if not api.topic.exists(topic):
        status.set_condition(
            SchemaConditionType.TopicReady,
            False,
            reason=SchemaReason.TopicNotFound.name,
            message=SchemaReason.TopicNotFound,
        )
        status.set_phase(SchemaPhase.Failed)
        raise kopf.TemporaryError(
            f"Topic '{model.tenant}/{model.namespace}/{model.topic}' not found in Pulsar",
            delay=ERROR_DELAY,
        )
    else:
        status.set_condition(SchemaConditionType.TopicReady, True)

    ################################
    ## Create Schema API instance ##
    ################################
    # Create a Schema instance needed by the API wrapper
    schema = Schema.from_spec(model)

    # Attempt to update
    try:
        api.schema.update(schema)
        status.set_condition(SchemaConditionType.SchemaInSync, True)
    except IncompatibleSchemaException:
        status.set_condition(
            SchemaConditionType.SchemaInSync,
            False,
            reason=SchemaReason.IncompatibleSchema.name,
            message=SchemaReason.IncompatibleSchema,
        )
        status.set_phase(SchemaPhase.Failed)
        raise kopf.PermanentError(SchemaReason.IncompatibleSchema)
    except ParsingException as e:
        status.set_condition(
            SchemaConditionType.SchemaInSync,
            False,
            reason=SchemaReason.ResponseParsingError.name,
            message=f"{SchemaReason.ResponseParsingError}: {e}",
        )
        status.set_phase(SchemaPhase.Failed)
        raise kopf.PermanentError(f"{SchemaReason.ResponseParsingError}: {e}")
    except APIException as e:
        status.set_condition(
            SchemaConditionType.SchemaInSync,
            False,
            reason=SchemaReason.UnknownError.name,
            message=str(e),
        )
        status.set_phase(SchemaPhase.Failed)
        raise kopf.PermanentError(f"Got an API error: {e}")

    #######################
    ## Set correct phase ##
    #######################
    if status.conditions_ok():
        status.set_phase(SchemaPhase.Ready)
        status.observedGeneration = body.meta.get("generation")


####################
## Delete Handler ##
####################
@kopf.on.delete("neuron.isf", "neuronschemas", annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def delete(
    status: NeuronStatus, memo: kopf.Memo, body: kopf.Body, logger: kopf.Logger, **_
):
    model = models.SchemaSpec(**body.spec)
    if model.lifecyclePolicy == models.LifecyclePolicy.CleanUpAfterDeletion:
        # Get Pulsar client from memo
        pulsar_client = memo.get("pulsar_client")
        api: API
        if pulsar_client and type(pulsar_client) == API:
            api = pulsar_client
        else:
            raise kopf.PermanentError("No pulsar client available")
        schema = Schema.from_spec(model)

        try:
            if api.schema.exists(schema):
                try:
                    api.schema.delete(schema)
                except Exception as e:
                    status.set_condition(
                        SchemaConditionType.SchemaInSync,
                        False,
                        reason=SchemaReason.DeleteFailed.name,
                        message=str(e),
                    )
                    status.set_phase(SchemaPhase.Pending)
                    raise kopf.TemporaryError(f"Unable to delete schema: {e}", delay=10)
        except APIException as e:
            logger.warn(f"Unable to check schema existence: {e.message}")
            logger.warn("Releasing resource anyway.")
