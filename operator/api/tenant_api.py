from .api import BaseAPI, APIException, APIRequestType
from models import TenantSpec, PulsarTenantSettings
from pydantic import Field


class TenantNotFoundException(Exception):
    pass


class ParsingException(Exception):
    pass


class Tenant(PulsarTenantSettings):
    name: str = Field(exclude=True)

    @classmethod
    def from_spec(cls, spec: TenantSpec) -> "Tenant":
        settings: dict = {}
        if spec.settings != None:
            settings = spec.settings.dict()

        return cls(name=spec.tenant, **settings)


class TenantAPI(BaseAPI):
    __base_url__: str

    def exists(self, tenant: Tenant) -> bool:
        try:
            t = self.get(tenant)
            return t != None
        except TenantNotFoundException:
            return False

    def get(self, tenant: Tenant) -> Tenant:
        url = "{base_url}/tenants/{name}".format(
            base_url=self.__base_url__,
            name=tenant.name,
        )

        r = self._get(url)

        if r.status_code == 200:
            try:
                settings = r.json()
                return Tenant(name=tenant.name, **settings)
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            try:
                self._handle_error(r)
            except APIException as e:
                if e.status_code == 404:
                    raise TenantNotFoundException()
                raise e

    def create(self, tenant: Tenant) -> Tenant:
        url = "{base_url}/tenants/{name}".format(
            base_url=self.__base_url__,
            name=tenant.name,
        )

        r = self._put(url, json=tenant.api_dict())

        if 200 <= r.status_code <= 204:
            return self.get(tenant)
        else:
            self._handle_error(r)

    def update(self, tenant: Tenant) -> Tenant:
        url = "{base_url}/tenants/{name}".format(
            base_url=self.__base_url__,
            name=tenant.name,
        )

        r = self._post(url, json=tenant.api_dict())

        if 200 <= r.status_code <= 204:
            return self.get(tenant)
        else:
            self._handle_error(r)

    def delete(self, tenant: Tenant) -> None:
        url = "{base_url}/tenants/{name}".format(
            base_url=self.__base_url__,
            name=tenant.name,
        )

        r = self._delete(url)

        if r.status_code != 204:
            self._handle_error(r)
