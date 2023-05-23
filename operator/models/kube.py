from .gen import (
    Status,
    StatusCondition,
)
from pydantic import BaseModel
from typing import Optional, Union, Any, Type, TYPE_CHECKING
from enum import Enum
from functools import wraps

# To make the linters happy :)
if TYPE_CHECKING:
    _Base = BaseModel
else:
    _Base = object


class StatusBase(_Base):
    conditions = []

    def __init__(self, phase: Optional[str] = None, **kwargs):
        if phase == None:
            phase = "Pending"

        super().__init__(phase=phase, **kwargs)

    def dict(self, exclude_none: bool = True, **kwargs):
        return super().dict(exclude_none=exclude_none, **kwargs)

    def set_condition(
        self,
        type: Enum,
        status: bool = False,
        reason: Union[None, str, Enum] = None,
        message: Optional[str] = None,
    ):
        res: Optional[str] = None
        # Convert reason Enum to string
        if isinstance(reason, Enum):
            if isinstance(reason.value, str):
                res = reason.value
            else:
                res = reason.name
        elif isinstance(reason, str):
            res = reason

        for i in range(len(self.conditions)):
            condition = self.conditions[i]

            if condition.type == type.value:
                self.conditions[i] = StatusCondition(
                    status=str(status), type=type.value, reason=res, message=message
                )
                return

        self.conditions.append(
            StatusCondition(
                status=str(status), type=type.value, reason=res, message=message
            )
        )

    def get_condition(self, type: Enum) -> bool:
        for condition in self.conditions:
            if condition.type == type.value:
                return condition.status == "True"

        return False

    def conditions_ok(self) -> bool:
        return all([c.status == "True" for c in self.conditions])

    def set_phase(self, val: Enum):
        self.phase = val.value


class NeuronStatus(StatusBase, Status):
    pass


# Types needed for type checking below
NeuronStatusType: type = Type[NeuronStatus]

# Automatic status handler
# This decorator will replace the `status` parameter passed on to the
# kopf handler with a wrapped dataclass instance.
# This makes it easier to work with rather than checking an untyped dict.
#
# Usage:
#   @kopf.on.update('neuron.isf', 'neuronconnections')
#   @status_handler(NeuronStatus)
#   def my_handler(status: NeuronStatus, **_):
#     status.phase = "Ready"
#
# Whatever fields are set in the status instance will automatically be
# patched if handler exists successfully.
def status_handler(
    cls: NeuronStatusType = NeuronStatus,
    auto_update: bool = True,
):
    def wrap_handler(handler):
        @wraps(handler)
        def wrapper(**kwargs):
            exc: Optional[Exception] = None
            res: Any = None

            # Fetch status from kopf kwargs
            _status = kwargs["status"]

            # Replace status in kwargs with Status class
            kwargs["status"] = cls(**_status)

            # Call actual hander
            try:
                res = handler(**kwargs)
            except Exception as e:
                exc = e

            # Fetch processed status back from kwargs
            status = kwargs["status"]

            # Put old status back
            kwargs["status"] = _status

            if auto_update:
                # Fetch patch object from kopf kwargs
                patch = kwargs["patch"]
                # Patch status
                patch["status"] = status.dict(exclude_none=True)

            # If there was an exception caught we throw it now
            if exc != None:
                raise exc

            # Return output from handler
            return res

        return wrapper

    return wrap_handler
