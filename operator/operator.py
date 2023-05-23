import kopf
import os
import sys
import api
import kubernetes.client
import kubernetes.config
from kubernetes.client.rest import ApiException
from handlers import *

CONFIG_CLUSTER_NAME = "CLUSTER_NAME"
CONFIG_PULSAR_SERVICE_NAME = "PULSAR_SERVICE_NAME"
CONFIG_NAMESPACE = "PULSAR_NAMESPACE"
CONFIG_PULSAR_API_URL = "PULSAR_API_URL"
CONFIG_PULSAR_API_SSL_SNI = "PULSAR_API_SSL_SNI"


class ServiceSpecNotFoundException(Exception):
    pass


class ServicePortNotFoundException(Exception):
    pass


def generate_url(svc: str, namespace: str):
    # Initially we need to load kubernetes config
    kubernetes.config.load_config()

    svc_spec: kubernetes.client.V1ServiceSpec

    with kubernetes.client.ApiClient() as api_client:
        api_instance = kubernetes.client.CoreV1Api(api_client)

        api_response = api_instance.read_namespaced_service(svc, namespace)

        if api_response.spec != None:
            svc_spec = api_response.spec
        else:
            raise ServiceSpecNotFoundException(f"No spec in service {namespace}/{svc}")

    if svc_spec.ports != None:
        proto = "https"
        port = next((p for p in svc_spec.ports if p.name == proto), None)
        if not port:
            proto = "http"
            port = next((p for p in svc_spec.ports if p.name == proto), None)

        if port:
            return f"{proto}://{svc}.{namespace}.svc:{port.port}/admin/v2"

    raise ServicePortNotFoundException("Neither https not http ports found")


@kopf.on.startup()  # type: ignore
def configure(
    settings: kopf.OperatorSettings, memo: kopf.Memo, logger: kopf.Logger, **_
):
    # Store runtime configuration
    cluster_name = os.environ.get("CLUSTER_NAME")
    if not CONFIG_CLUSTER_NAME in os.environ:
        logger.error(
            f"No cluster name specified! Set environment variable {CONFIG_CLUSTER_NAME}"
        )
        sys.exit(1)

    service_name = os.environ.get(
        CONFIG_PULSAR_SERVICE_NAME, f"{cluster_name}-neuron-pulsar-proxy"
    )
    service_namespace = os.environ.get(
        CONFIG_NAMESPACE, f"{cluster_name}-neuron-pulsar"
    )

    memo["cluster_name"] = os.environ.get(CONFIG_CLUSTER_NAME)
    memo["pulsar_service_name"] = service_name
    memo["pulsar_namespace"] = service_namespace

    api_url = os.environ.get(CONFIG_PULSAR_API_URL)
    if not api_url:
        # Construct an API URL from proxy service and create a Pulsar client
        try:
            api_url = generate_url(service_name, service_namespace)
        except ApiException as e:
            if e.status == 404:
                logger.error(f"Service {service_namespace}/{service_name} not found")
                sys.exit(1)
            else:
                raise e

    logger.info(f"Using Pulsar API URL {api_url}")
    memo["pulsar_client"] = api.API(
        api_url, sni=os.environ.get(CONFIG_PULSAR_API_SSL_SNI)
    )

    # Setup Neuron "branding" to finalizers and various internal annotations
    settings.persistence.finalizer = f"{cluster_name}.neuron.rbi.tech/finalizer"
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix="neuron.rbi.tech",
        key="last-handled-configuration",
    )
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix="neuron.rbi.tech"
    )

    # Disable event posting
    settings.posting.enabled = False
