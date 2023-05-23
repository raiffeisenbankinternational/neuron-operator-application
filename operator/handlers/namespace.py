import kopf
import models
from models import NeuronStatus, status_handler
from api import API, Tenant, Namespace, APIException
from .common import CLUSTER_ANNOTATION, CommonConditionType
from enum import Enum


ERROR_DELAY = 5


class NamespaceConditionType(str, Enum):
    TenantReady = "TenantReady"
    NamespaceInSync = "NamespaceInSync"


class NamespacePhase(str, Enum):
    Pending = "Pending"
    Ready = "Ready"
    Failed = "Failed"


class NamespaceReason(str, Enum):
    TenantNotFound = "Tenant not found in Pulsar cluster"
    DeleteFailed = "Delete failed"


############################
## Main Namespace Handler ##
############################
def cluster_check(value: str, memo: kopf.Memo, **_):
    return value == memo.get("cluster_name")


@kopf.on.update("neuron.isf", "neuronnamespaces", retries=3, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.resume("neuron.isf", "neuronnamespaces", retries=3, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.timer("neuron.isf", "neuronnamespaces", retries=3, initial_delay=60, interval=600, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def namespace_handler(
    status: NeuronStatus,
    memo: kopf.Memo,
    meta: dict,
    spec: dict,
    **_,
):
    # At this point we can fix ClusterTargetOK condition
    status.set_condition(CommonConditionType.ClusterTargetOK, True)

    # Mapping spec to a Python native model class
    model = models.NamespaceSpec(**spec)

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
            NamespaceConditionType.TenantReady,
            False,
            reason=NamespaceReason.TenantNotFound.name,
            message=NamespaceReason.TenantNotFound,
        )
        status.set_phase(NamespacePhase.Failed)
        raise kopf.TemporaryError(
            f"Tenant '{model.tenant}' not found in Pulsar", delay=ERROR_DELAY
        )
    else:
        status.set_condition(NamespaceConditionType.TenantReady, True)

    # Create a Namespace instance needed by the API wrapper
    ns = Namespace.from_spec(model)

    # Namespace doesn't already exist
    if not api.namespace.exists(ns):
        try:
            api.namespace.create(ns)
        except APIException as e:
            status.set_condition(
                NamespaceConditionType.NamespaceInSync, False, message=str(e)
            )
            status.set_phase(NamespacePhase.Pending)
            raise kopf.TemporaryError(
                f"Unable to create namespace: {e}", delay=ERROR_DELAY
            )

    try:
        api.namespace.update(ns)
        api.namespace.sync_permissions(ns)
    except APIException as e:
        status.set_condition(
            NamespaceConditionType.NamespaceInSync, False, message=str(e)
        )
        status.set_phase(NamespacePhase.Pending)
        raise kopf.TemporaryError(f"Unable to sync namespace: {e}", delay=ERROR_DELAY)

    # If we reached this far everything should be fine
    status.set_condition(NamespaceConditionType.NamespaceInSync, True)

    #######################
    ## Set correct phase ##
    #######################
    if status.conditions_ok():
        status.set_phase(NamespacePhase.Ready)
        status.observedGeneration = meta.get("generation")


####################
## Delete Handler ##
####################
@kopf.on.delete("neuron.isf", "neuronnamespaces", annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def delete(
    status: NeuronStatus, memo: kopf.Memo, body: kopf.Body, logger: kopf.Logger, **_
):
    model = models.NamespaceSpec(**body.spec)
    if model.lifecyclePolicy == models.LifecyclePolicy.CleanUpAfterDeletion:
        # Get Pulsar client from memo
        pulsar_client = memo.get("pulsar_client")
        api: API
        if pulsar_client and type(pulsar_client) == API:
            api = pulsar_client
        else:
            raise kopf.PermanentError("No pulsar client available")

        namespace = Namespace.from_spec(model)

        try:
            if api.namespace.exists(namespace):
                try:
                    api.namespace.delete(namespace)
                except Exception as e:
                    status.set_condition(
                        NamespaceConditionType.NamespaceInSync,
                        False,
                        reason=NamespaceReason.DeleteFailed.name,
                        message=str(e),
                    )
                    status.set_phase(NamespacePhase.Pending)
                    raise kopf.TemporaryError(
                        f"Unable to delete namespace: {e}", delay=10
                    )
        except APIException as e:
            logger.warn(f"Unable to check namespace existence: {e.message}")
            logger.warn("Releasing resource anyway.")
