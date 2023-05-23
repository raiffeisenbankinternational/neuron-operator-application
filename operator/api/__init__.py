from .api import APIException
from .tenant_api import TenantAPI, Tenant
from .namespace_api import NamespaceAPI, Namespace
from .topic_api import TopicAPI, Topic
from .schema_api import SchemaAPI, Schema
from typing import Optional


class API:
    tenant: TenantAPI
    namespace: NamespaceAPI
    topic: TopicAPI
    schema: SchemaAPI

    def __init__(self, base_url: str, sni: Optional[str] = None):
        self.tenant = TenantAPI(base_url, sni=sni)
        self.namespace = NamespaceAPI(base_url, sni=sni)
        self.topic = TopicAPI(base_url, sni=sni)
        self.schema = SchemaAPI(base_url, sni=sni)
