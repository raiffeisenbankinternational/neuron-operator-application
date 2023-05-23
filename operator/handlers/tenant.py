import kopf
import models
from models import NeuronStatus, status_handler
from api import API, Tenant, APIException
from .common import CLUSTER_ANNOTATION, CommonConditionType
from enum import Enum


class TenantConditionType(str, Enum):
    ConnectionOK = "ConnectionOK"
    TenantInSync = "TenantInSync"


class TenantPhase(str, Enum):
    Pending = "Pending"
    Ready = "Ready"
    Failed = "Failed"


#########################
## Main Tenant Handler ##
#########################
def cluster_check(value: str, memo: kopf.Memo, **_):
    return value == memo.get("cluster_name")


@kopf.on.update("neuron.isf", "neurontenants", annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.resume("neuron.isf", "neurontenants", annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@kopf.on.timer("neuron.isf", "neurontenants", interval=600, initial_delay=60, annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def tenant_handler(
    status: NeuronStatus,
    memo: kopf.Memo,
    meta: dict,
    spec: dict,
    **_,
):
    # Create a backoff if retries are more than 10
    delay = 5

    # At this point we can fix ClusterTargetOK condition
    status.set_condition(CommonConditionType.ClusterTargetOK, True)

    # Mapping spec to a Python native model class
    model = models.TenantSpec(**spec)

    # Get Pulsar client from memo
    pulsar_client = memo.get("pulsar_client")
    api: API
    if pulsar_client and type(pulsar_client) == API:
        api = pulsar_client
    else:
        raise kopf.PermanentError("No pulsar client available")

    tenant = Tenant.from_spec(model)

    # Tenant doesn't already exist
    if not api.tenant.exists(tenant):
        try:
            api.tenant.create(tenant)
        except APIException as e:
            status.set_condition(
                TenantConditionType.TenantInSync, False, message=str(e)
            )
            status.set_phase(TenantPhase.Pending)
            raise kopf.TemporaryError(f"Unable to create tenant: {e}", delay=delay)

    try:
        api.tenant.update(tenant)
    except APIException as e:
        status.set_condition(TenantConditionType.TenantInSync, False, message=str(e))
        status.set_phase(TenantPhase.Pending)
        raise kopf.TemporaryError(f"Unable to update tenant: {e}", delay=delay)

    # If we reached this far everything should be fine
    status.set_condition(TenantConditionType.TenantInSync, True)

    #######################
    ## Set correct phase ##
    #######################
    if status.conditions_ok():
        status.set_phase(TenantPhase.Ready)
        status.observedGeneration = meta.get("generation")


####################
## Delete Handler ##
####################
@kopf.on.delete("neuron.isf", "neurontenants", annotations={CLUSTER_ANNOTATION: cluster_check})  # type: ignore
@status_handler(NeuronStatus)
def delete(
    status: NeuronStatus, memo: kopf.Memo, body: kopf.Body, logger: kopf.Logger, **_
):
    model = models.TenantSpec(**body.spec)
    if model.lifecyclePolicy == models.LifecyclePolicy.CleanUpAfterDeletion:
        # Get Pulsar client from memo
        pulsar_client = memo.get("pulsar_client")
        api: API
        if pulsar_client and type(pulsar_client) == API:
            api = pulsar_client
        else:
            raise kopf.PermanentError("No pulsar client available")
        tenant = Tenant.from_spec(model)

        try:
            if api.tenant.exists(tenant):
                try:
                    api.tenant.delete(tenant)
                except Exception as e:
                    status.set_condition(
                        TenantConditionType.TenantInSync,
                        False,
                        reason="DeleteFailed",
                        message=str(e),
                    )
                    status.set_phase(TenantPhase.Pending)
                    raise kopf.TemporaryError(f"Unable to delete tenant: {e}", delay=10)
        except APIException as e:
            logger.warn(f"Unable to check tenant existence: {e.message}")
            logger.warn("Releasing resource anyway.")
