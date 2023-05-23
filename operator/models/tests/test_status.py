from ..kube import *
from enum import Enum


class ConditionType(str, Enum):
    Condition1 = "Condition1"
    Condition2 = "Condition2"
    Condition3 = "Condition3"


class Phase(str, Enum):
    Pending = "Pending"
    Ready = "Ready"


##################
## NeuronStatus ##
##################
neuron_status_input = {
    "phase": "Pending",
    "conditions": [
        {
            "type": ConditionType.Condition1.value,
            "status": "True",
        },
        {
            "type": ConditionType.Condition2.value,
            "status": "False",
        },
    ],
}


def test_neuron_status_parse():
    status = NeuronStatus(**neuron_status_input)
    assert status.phase == "Pending"
    assert status.conditions != None and len(status.conditions) == 2
    assert status.conditions[0].type == ConditionType.Condition1.value
    assert status.conditions[0].status == "True"
    assert status.conditions[1].type == ConditionType.Condition2.value
    assert status.conditions[1].status == "False"


def test_neuron_status_get_condition():
    status = NeuronStatus(**neuron_status_input)
    assert status.get_condition(ConditionType.Condition1) == True
    assert status.get_condition(ConditionType.Condition2) == False


def test_neuron_status_set_condition():
    status = NeuronStatus(**neuron_status_input)
    status.set_condition(ConditionType.Condition2, True)
    status.set_condition(ConditionType.Condition3, False, reason="fail")
    assert status.get_condition(ConditionType.Condition1) == True
    assert status.get_condition(ConditionType.Condition2) == True
    assert status.get_condition(ConditionType.Condition3) == False


def test_neuron_status_conditions_ok():
    status = NeuronStatus(**neuron_status_input)
    assert status.conditions_ok() == False
    status.set_condition(ConditionType.Condition2, True)
    assert status.conditions_ok() == True


def test_neuron_status_to_dict():
    expected = {
        "phase": "Ready",
        "conditions": [
            {
                "type": ConditionType.Condition1.value,
                "status": "True",
            },
            {
                "type": ConditionType.Condition2.value,
                "status": "True",
            },
            {
                "type": ConditionType.Condition3.value,
                "status": "False",
                "reason": "fail",
            },
        ],
    }
    status = NeuronStatus(**neuron_status_input)
    status.set_phase(Phase.Ready)
    status.set_condition(ConditionType.Condition2, True)
    status.set_condition(ConditionType.Condition3, False, reason="fail")
    assert status.dict() == expected
