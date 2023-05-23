from .api import BaseAPI, APIRequestType
from models import TopicSpec, PulsarTopicPolicies, RolePermissionEnum
from pydantic import Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class TopicNotFoundException(Exception):
    pass


class ParsingException(Exception):
    pass


class Topic(PulsarTopicPolicies):
    name: str = Field(exclude=True)
    tenant: str = Field(exclude=True)
    namespace: str = Field(exclude=True)
    persistent: bool = Field(True, exclude=True)
    partitions: int = Field(0, exclude=True)
    role_permissions: Optional[Dict[str, List[RolePermissionEnum]]] = Field(
        exclude=True
    )

    @classmethod
    def from_spec(cls, spec: TopicSpec) -> "Topic":
        policies: dict = {}
        if spec.policies != None:
            policies = spec.policies.dict()

        return cls(
            name=spec.topic,
            namespace=spec.namespace,
            tenant=spec.tenant,
            persistent=spec.persistent or True,
            partitions=spec.partitions or 0,
            role_permissions=spec.rolePermissions,
            **policies,
        )

    @property
    def full_name(self):
        return "{persistence}://{tenant}/{namespace}/{name}".format(
            persistence="persistent" if self.persistent else "non-persistent",
            tenant=self.tenant,
            namespace=self.namespace,
            name=self.name,
        )

    @property
    def permissions(self) -> Dict[str, List[str]]:
        if self.role_permissions != None:
            return {
                k: [p.value for p in perms]
                for k, perms in self.role_permissions.items()
            }
        return {}


class TopicAPI(BaseAPI):
    __base_url__: str

    __config__: Dict[str, Any] = {}
    __config_fetched__: datetime = datetime.min

    def exists(self, topic: Topic) -> bool:
        url = "{base_url}/{persistence}/{tenant}/{namespace}".format(
            base_url=self.__base_url__,
            persistence="persistent" if topic.persistent else "non-persistent",
            tenant=topic.tenant,
            namespace=topic.namespace,
        )

        if topic.partitions > 0:
            url = f"{url}/partitioned"

        r = self._get(url)

        if r.status_code == 200:
            try:
                topics = r.json()
                assert isinstance(topics, list)
                return topic.full_name in topics
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            self._handle_error(r)

    def create(self, topic: Topic) -> None:
        url = "{base_url}/{persistence}/{tenant}/{namespace}/{topic}".format(
            base_url=self.__base_url__,
            persistence="persistent" if topic.persistent else "non-persistent",
            tenant=topic.tenant,
            namespace=topic.namespace,
            topic=topic.name,
        )
        body: Optional[int] = None

        if topic.partitions > 0:
            url = f"{url}/partitions"
            body = topic.partitions

        r = self._put(url, json=body)

        if not (200 <= r.status_code <= 204):
            self._handle_error(r)

    def update(self, topic: Topic) -> None:
        base_url = "{base_url}/{persistence}/{tenant}/{namespace}/{topic}".format(
            base_url=self.__base_url__,
            persistence="persistent" if topic.persistent else "non-persistent",
            tenant=topic.tenant,
            namespace=topic.namespace,
            topic=topic.name,
        )

        for _, uri in topic.api_uris().items():
            method, url = uri.endpoint(base_url)

            r = self._request(APIRequestType(method), url, json=uri.value)

            if 200 <= r.status_code <= 204:
                continue
            else:
                self._handle_error(r)

    def delete(self, topic: Topic) -> None:
        url = "{base_url}/{persistence}/{tenant}/{namespace}/{topic}".format(
            base_url=self.__base_url__,
            persistence="persistent" if topic.persistent else "non-persistent",
            tenant=topic.tenant,
            namespace=topic.namespace,
            topic=topic.name,
        )

        if topic.partitions > 0:
            url = f"{url}/partitions"

        r = self._delete(url)

        if r.status_code != 204:
            self._handle_error(r)

    # runtime_config is a property that fetches the runtime_config
    # from Pulsar API and caches it for 1 minute.
    @property
    def runtime_config(self) -> Dict[str, Any]:
        if (
            self.__config__ is None
            or datetime.now() > self.__config_fetched__ + timedelta(minutes=1)
        ):
            self.__config__ = self.get_runtime_config()
            self.__config_fetched__ = datetime.now()

        return self.__config__

    def topic_level_policies_enabled(self) -> bool:
        return (
            "topicLevelPoliciesEnabled" in self.runtime_config
            and self.runtime_config["topicLevelPoliciesEnabled"] == "true"
        )

    def permissions(self, topic: Topic) -> Dict[str, List[str]]:
        # Pulsar topic permissions API retrieves the effective permissions for a topic. These permissions are defined by the permissions set at then namespace level combined (union) with any eventual specific permission set on the topic.
        # To get only permissions set on topic level we subtract the namespace permissions from the topic ones.

        # namespace permissions
        url = "{base_url}/namespaces/{tenant}/{namespace}/permissions".format(
            base_url=self.__base_url__,
            tenant=topic.tenant,
            namespace=topic.namespace,
        )


        r = self._get(url)
        if r.status_code == 200:
            try:
                namespacePermissions=r.json()
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")            
        else:
          self._handle_error(r)

        # topic permissions
        url = (
            "{base_url}/{persistence}/{tenant}/{namespace}/{topic}/permissions".format(
                base_url=self.__base_url__,
                persistence="persistent" if topic.persistent else "non-persistent",
                tenant=topic.tenant,
                namespace=topic.namespace,
                topic=topic.name,
            )
        )

        r = self._get(url)
        if r.status_code == 200:
            try:
                topicPermissions=r.json()
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")            

            # calculate delta
            permissions={}
            for key, value in topicPermissions.items():
                if namespacePermissions.get(key) == None:
                    permissions[key]=value
                else: # permission exists in namespacePermissions
                    action=list(set(value) - set(namespacePermissions.get(key)))
                    if action != []:
                        permissions[key]=action
            try:
                assert isinstance(permissions, dict)
                return permissions
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            self._handle_error(r)


    def sync_permissions(self, topic: Topic) -> None:
        current_permissions = self.permissions(topic)

        for role, perms in topic.permissions.items():
            self._set_role_permissions(topic, role, perms)

        for role in current_permissions.keys():
            if role not in topic.permissions:
                self._del_role_permissions(topic, role)

    def _set_role_permissions(
        self, topic: Topic, role: str, permissions: List[str]
    ) -> None:
        url = "{base_url}/{persistence}/{tenant}/{namespace}/{topic}/permissions/{role}".format(
            base_url=self.__base_url__,
            persistence="persistent" if topic.persistent else "non-persistent",
            tenant=topic.tenant,
            namespace=topic.namespace,
            topic=topic.name,
            role=role,
        )

        r = self._post(url, json=permissions)

        if not (200 <= r.status_code <= 204):
            self._handle_error(r)

    def _del_role_permissions(self, topic: Topic, role: str) -> None:
        url = "{base_url}/{persistence}/{tenant}/{namespace}/{topic}/permissions/{role}".format(
            base_url=self.__base_url__,
            persistence="persistent" if topic.persistent else "non-persistent",
            tenant=topic.tenant,
            namespace=topic.namespace,
            topic=topic.name,
            role=role,
        )

        r = self._delete(url)

        if not (200 <= r.status_code <= 204):
            # 412 is returned if we're trying to delete a role permission set
            # on namespace level exclusively.
            # We simply ignore this.
            if r.status_code == 412:
                return
            self._handle_error(r)
