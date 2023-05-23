from .api import BaseAPI, APIException, APIRequestType
from models import NamespaceSpec, PulsarNamespacePolicies, RolePermissionEnum
from pydantic import Field
from typing import Dict, List, Optional


class NamespaceNotFoundException(Exception):
    pass


class ParsingException(Exception):
    pass


class Namespace(PulsarNamespacePolicies):
    name: str = Field(exclude=True)
    tenant: str = Field(exclude=True)
    role_permissions: Optional[Dict[str, List[RolePermissionEnum]]] = Field(
        exclude=True
    )

    @classmethod
    def from_spec(cls, spec: NamespaceSpec) -> "Namespace":
        policies: dict = {}
        if spec.policies != None:
            policies = spec.policies.dict()

        return cls(
            name=spec.namespace,
            tenant=spec.tenant,
            role_permissions=spec.rolePermissions,
            **policies,
        )

    @property
    def permissions(self) -> Dict[str, List[str]]:
        if self.role_permissions != None:
            return {
                k: [p.value for p in perms]
                for k, perms in self.role_permissions.items()
            }
        return {}


class NamespaceAPI(BaseAPI):
    __base_url__: str

    def exists(self, namespace: Namespace) -> bool:
        try:
            t = self.get(namespace)
            return t != None
        except NamespaceNotFoundException:
            return False

    def get(self, namespace: Namespace) -> Namespace:
        url = "{base_url}/namespaces/{tenant}/{name}".format(
            base_url=self.__base_url__,
            tenant=namespace.tenant,
            name=namespace.name,
        )

        r = self._get(url)

        if r.status_code == 200:
            try:
                policies = r.json()
                return Namespace(
                    name=namespace.name, tenant=namespace.tenant, **policies
                )
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            try:
                self._handle_error(r)
            except APIException as e:
                if e.status_code == 404:
                    raise NamespaceNotFoundException()
                raise e

    def create(self, namespace: Namespace) -> Namespace:
        url = "{base_url}/namespaces/{tenant}/{name}".format(
            base_url=self.__base_url__,
            tenant=namespace.tenant,
            name=namespace.name,
        )

        r = self._put(url, json=namespace.api_dict())

        if 200 <= r.status_code <= 204:
            return self.get(namespace)
        else:
            self._handle_error(r)

    def update(self, namespace: Namespace) -> Namespace:
        base_url = "{base_url}/namespaces/{tenant}/{name}".format(
            base_url=self.__base_url__,
            tenant=namespace.tenant,
            name=namespace.name,
        )

        for _, uri in namespace.api_uris().items():
            method, url = uri.endpoint(base_url)

            r = self._request(APIRequestType(method), url, json=uri.value)

            if 200 <= r.status_code <= 204:
                continue
            else:
                self._handle_error(r)

        return self.get(namespace)

    def delete(self, namespace: Namespace) -> None:
        url = "{base_url}/namespaces/{tenant}/{name}".format(
            base_url=self.__base_url__,
            tenant=namespace.tenant,
            name=namespace.name,
        )

        r = self._delete(url)

        if r.status_code != 204:
            self._handle_error(r)

    def permissions(self, namespace: Namespace) -> Dict[str, List[str]]:
        url = "{base_url}/namespaces/{tenant}/{namespace}/permissions".format(
            base_url=self.__base_url__,
            tenant=namespace.tenant,
            namespace=namespace.name,
        )

        r = self._get(url)

        if r.status_code == 200:
            try:
                permissions = r.json()
                assert isinstance(permissions, dict)
                return permissions
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            self._handle_error(r)

    def sync_permissions(self, namespace: Namespace) -> None:
        current_permissions = self.permissions(namespace)

        for role, perms in namespace.permissions.items():
            self._set_role_permissions(namespace, role, perms)

        for role in current_permissions.keys():
            if role not in namespace.permissions:
                self._del_role_permissions(namespace, role)

    def _set_role_permissions(
        self, namespace: Namespace, role: str, permissions: List[str]
    ) -> None:
        url = "{base_url}/namespaces/{tenant}/{name}/permissions/{role}".format(
            base_url=self.__base_url__,
            tenant=namespace.tenant,
            name=namespace.name,
            role=role,
        )

        r = self._post(url, json=permissions)

        if not (200 <= r.status_code <= 204):
            self._handle_error(r)

    def _del_role_permissions(self, namespace: Namespace, role: str) -> None:
        url = "{base_url}/namespaces/{tenant}/{name}/permissions/{role}".format(
            base_url=self.__base_url__,
            tenant=namespace.tenant,
            name=namespace.name,
            role=role,
        )

        r = self._delete(url)

        if not (200 <= r.status_code <= 204):
            self._handle_error(r)
