import kopf
from models import NeuronStatus, status_handler
from enum import Enum


CLUSTER_ANNOTATION = "neuron.rbi.tech/cluster"


class CommonConditionType(str, Enum):
    ClusterTargetOK = "ClusterTargetOK"


class CommonPhase(str, Enum):
    Ready = "Ready"
    Pending = "Pending"
    Failed = "Failed"


class CommonReason(str, Enum):
    NoClusterTarget = (
        f"Neither spec.neuronClusterName nor {CLUSTER_ANNOTATION} annotation specified"
    )


def orphan_check(meta: kopf.Meta, spec: kopf.Spec, memo: kopf.Memo, **_):
    cluster_name = spec.get("neuronClusterName")
    annotation = meta.annotations.get(CLUSTER_ANNOTATION)
    return cluster_name == memo.get("cluster_name") and annotation == None


@kopf.on.create("neuron.isf", kopf.EVERYTHING, when=orphan_check)  # type: ignore
@kopf.on.update("neuron.isf", kopf.EVERYTHING, when=orphan_check)  # type: ignore
@kopf.on.resume("neuron.isf", kopf.EVERYTHING, when=orphan_check)  # type: ignore
@status_handler(NeuronStatus)
def annotation_handler(memo: kopf.Memo, patch: dict, **_):
    patch["metadata"] = {"annotations": {CLUSTER_ANNOTATION: memo.get("cluster_name")}}
