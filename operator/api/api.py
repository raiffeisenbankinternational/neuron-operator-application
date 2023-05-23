import requests
from urllib3 import HTTPConnectionPool, HTTPSConnectionPool
from abc import abstractmethod
from typing import Optional, Any, Union, Dict
from enum import Enum


class APIException(Exception):
    message: str
    status_code: int

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code


class ParsingException(Exception):
    pass


class APIRequestType(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


# This is needed to support HTTPS connections where the hostname
# in the certificate is different from the hostname used to initiate
# the connection. i.e. in-cluster we use service hostname but the
# pulsar broker has a certificate for external DNS.
#
# requests doesn't have any way of simply specifying the SNI to use
# for verification so we need to create an HTTPAdapter that will
# be used to verify all connections made to certain connection prefixes.
class HostnameCheckAdapter(requests.sessions.HTTPAdapter):
    __sni_hostname__: Optional[str] = None

    def __init__(self, sni: Optional[str] = None):
        super().__init__()
        self.__sni_hostname__ = sni

    def cert_verify(
        self,
        conn: Union[HTTPConnectionPool, HTTPSConnectionPool],
        url: str,
        verify: Union[None, str, bool],
        cert,
    ) -> bool:
        # Check that the conn is actually a HTTPSConnectionPool and
        # we have an SNI to verify against.
        if conn.scheme == "https" and self.__sni_hostname__:
            # Setting the `assert_hostname` instructs urllib3 that it
            # should check for that domain in the certification step.
            setattr(conn, "assert_hostname", self.__sni_hostname__)

        # Handover to HTTPAdapter's `cert_verify` method
        return super(HostnameCheckAdapter, self).cert_verify(conn, url, verify, cert)


class BaseAPI:
    __base_url__: str
    __token_path__: str = "/var/run/secrets/pulsar/TOKEN"
    __sni__: Optional[str] = None

    def __init__(
        self,
        base_url: str,
        token_path: Optional[str] = None,
        sni: Optional[str] = None,
    ):
        self.__base_url__ = base_url
        self.__sni__ = sni
        if token_path:
            self.__token_path__ = token_path

    def _request(
        self,
        method: APIRequestType,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        session: Optional[requests.Session] = None,
    ) -> requests.Response:
        if not session:
            # Create a session
            session = requests.Session()

        # Mount the HostnameCheckAdapter for base url
        session.mount(self.__base_url__, HostnameCheckAdapter(sni=self.__sni__))

        # Create the request
        req = requests.Request(method.value, url, json=json, data=data)
        prepped = req.prepare()

        # Read token file
        try:
            with open(self.__token_path__, "r") as token_data:
                token = token_data.read()
                prepped.headers["Authorization"] = f"Bearer {token}"
        except FileNotFoundError:
            pass

        # Send request and return results
        return session.send(prepped)

    def _get(self, url: str, **kwargs) -> requests.Response:
        return self._request(APIRequestType.GET, url, **kwargs)

    def _put(self, url: str, **kwargs) -> requests.Response:
        return self._request(APIRequestType.PUT, url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        return self._request(APIRequestType.POST, url, **kwargs)

    def _delete(self, url: str, **kwargs) -> requests.Response:
        return self._request(APIRequestType.DELETE, url, **kwargs)

    def _handle_error(self, res: requests.Response):
        try:
            body = res.json()
        except Exception:
            raise APIException(
                f"Unknown error. status_code='{res.status_code}' body='{res.text}'",
                res.status_code,
            )

        if "reason" in body:
            raise APIException(body.get("reason"), res.status_code)

        raise APIException(res.text, res.status_code)

    def get_runtime_config(self) -> Dict[str, Any]:
        url = f"{self.__base_url__}/brokers/configuration/runtime"

        r = self._get(url)

        if r.status_code == 200:
            try:
                config = r.json()
                assert isinstance(config, dict)
                return config
            except Exception as e:
                raise ParsingException(f"Unable to parse response: {e}")
        else:
            self._handle_error(r)

    @abstractmethod
    def exists(self, spec):
        pass

    @abstractmethod
    def get(self, spec):
        pass

    @abstractmethod
    def create(self, spec):
        pass

    @abstractmethod
    def update(self, spec):
        pass

    @abstractmethod
    def delete(self, spec):
        pass
