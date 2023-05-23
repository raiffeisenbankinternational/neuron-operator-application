from models import TenantSpec
from ..tenant_api import TenantAPI, Tenant
import requests_mock
import json


def test_parse():
    tenant = Tenant(
        name="sample",
        **{
            "adminRoles": ["admin"],
            "allowedClusters": ["dev01"],
        }
    )

    assert tenant.name == "sample"
    assert tenant.adminRoles == ["admin"]
    assert tenant.allowedClusters == ["dev01"]


def test_api_dict():
    tenant = Tenant(
        name="sample",
        **{
            "adminRoles": ["admin"],
            "allowedClusters": ["dev01"],
        }
    )
    expected = {
        "adminRoles": ["admin"],
        "allowedClusters": ["dev01"],
    }

    assert tenant.api_dict() == expected


def test_from_spec():
    tenant = Tenant.from_spec(
        TenantSpec(
            **{
                "tenant": "sample",
                "settings": {
                    "adminRoles": ["admin"],
                    "allowedClusters": ["dev01"],
                },
            }
        )
    )

    assert tenant.name == "sample"
    assert tenant.adminRoles == ["admin"]
    assert tenant.allowedClusters == ["dev01"]


#########
## GET ##
#########
def test_get():
    def handler(req, ctx):
        ctx.status_code = 200
        return json.dumps(
            {
                "adminRoles": [],
                "allowedClusters": ["dev01"],
            }
        )

    ns = Tenant(name="sample", **{})
    api = TenantAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.get("http://localhost:8080/admin/v2/tenants/sample", text=handler)

        tenant = api.get(ns)

        assert tenant.name == "sample"
        assert tenant.adminRoles == []
        assert tenant.allowedClusters == ["dev01"]


############
## CREATE ##
############
def test_create():
    ret = {
        "adminRoles": ["admin"],
        "allowedClusters": ["dev01"],
    }

    def handler(req, ctx):
        ctx.status_code = 200
        return json.dumps(ret)

    tenant = Tenant(
        name="sample",
        **{
            "adminRoles": ["admin"],
            "allowedClusters": ["dev01"],
        }
    )
    expected = {
        "adminRoles": ["admin"],
        "allowedClusters": ["dev01"],
    }
    api = TenantAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.put(
            "http://localhost:8080/admin/v2/tenants/sample",
            json=expected,
            status_code=204,
        )
        m.get("http://localhost:8080/admin/v2/tenants/sample", text=handler)
        t2 = api.create(tenant)

        assert t2.api_dict() == expected
        assert t2.adminRoles == tenant.adminRoles
        assert t2.allowedClusters == tenant.allowedClusters


############
## UPDATE ##
############
def test_update():
    ret = {
        "adminRoles": ["admin"],
        "allowedClusters": ["dev01"],
    }

    def handler(req, ctx):
        ctx.status_code = 200
        return json.dumps(ret)

    tenant = Tenant(
        name="sample",
        **{
            "adminRoles": ["admin"],
            "allowedClusters": ["dev01"],
        }
    )
    expected = {
        "adminRoles": ["admin"],
        "allowedClusters": ["dev01"],
    }
    api = TenantAPI("http://localhost:8080/admin/v2")
    with requests_mock.Mocker() as m:
        m.post(
            "http://localhost:8080/admin/v2/tenants/sample",
            json=expected,
            status_code=204,
        )
        m.get("http://localhost:8080/admin/v2/tenants/sample", text=handler)
        t2 = api.update(tenant)

        assert t2.api_dict() == expected
        assert t2.adminRoles == tenant.adminRoles
        assert t2.allowedClusters == tenant.allowedClusters
