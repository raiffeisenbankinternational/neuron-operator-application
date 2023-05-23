import requests
from .gen import (
    TenantSettings,
    NamespacePolicies,
    TopicPolicies,
)
from dataclasses import dataclass
from pydantic import BaseModel
from typing import Dict, Tuple, Any, TYPE_CHECKING
from enum import Enum
from humps.main import camelize

# To make the linters happy :)
if TYPE_CHECKING:
    _Base = BaseModel
else:
    _Base = object


@dataclass
class APIValue:
    uri: str
    method: str = "POST"
    value: Any = None

    def request(self, base_url: str) -> requests.Request:
        url = f"{base_url}{self.uri}"
        return requests.Request(self.method, url, json=self.value)

    def endpoint(self, base_url: str) -> Tuple[str, str]:
        return (self.method, f"{base_url}{self.uri}")


class PulsarBase(_Base):
    def api_dict(self) -> dict:
        return self.dict(by_alias=True, exclude_none=True)
    
    # Apply the overrides from apis definition
    def api_uris(self) -> Dict[str, APIValue]:
        ret = {}
        for field in self.__fields__:
            key = field
            value = getattr(self, field)
            field_info = self.__fields__[field].field_info
            extra = field_info.extra
            uri: str = extra.get("uri", f"/{camelize(key)}")
            method: str = extra.get("method", "POST")

            if field_info.exclude or extra.get("immutable") or value == None:
                continue

            if field_info.alias:
                key = field_info.alias

            if hasattr(value, "__class__") and issubclass(value.__class__, BaseModel):
                value = BaseModel.dict(value, exclude_none=True)

            if isinstance(value, Enum):
                value = value.value

            ret[key] = APIValue(uri, method, value)

        return ret


class PulsarTenantSettings(PulsarBase, TenantSettings):
    pass


class PulsarNamespacePolicies(PulsarBase, NamespacePolicies):
    pass


class PulsarTopicPolicies(PulsarBase, TopicPolicies):
    pass
