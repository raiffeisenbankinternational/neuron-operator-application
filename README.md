# Neuron Operator

🚧 Work in progress 🚧

Kubernetes used for deploying Tenants, Namespaces, Topics and Schemas to a Pulsar cluster.

## Deployment

See [manifest](https://code.rbi.tech/raiffeisen/neuron-operator-manifest) repository for deploying Neuron Operator in Cortex.

## Usage

The Neuron Operator is intended to be deployed to Cortex targeting a single Pulsar cluster. This means that if there are multiple Pulsar clusters running in a Cortex cluster, multiple instances of the Neuron Operator must be deployed.

Each instance of the Neuron Operator sets a cluster name (environment variable `CLUSTER_NAME` or `clusterName` in helm manifest repository) that's used to select which Pulsar cluster the resource should be deployed to. This cluster name is therefor used a selector in all the CRDs for the target, as an annotation `neuron.rbi.tech/cluster` or `.spec.neuronClusterName` field.

Once the operator has been deployed the following resources can be deployed.

### 1. NeuronTenant

`NeuronTenant` maps directly to a tenant in Pulsar.

```yaml
apiVersion: neuron.isf/v1alpha1
kind: NeuronTenant
metadata:
  name: my-tenant
spec:
  tenant: rbi
  neuronClusterName: dev01
  lifecyclePolicy: KeepAfterDeletion
  settings:
    allowedClusters:
    - dev01
    adminRoles:
    - admin
```

This resource creates a tenant in Pulsar called `rbi`. Notice that the name of the Cortex resource is decoupled from the resulting tenant in Pulsar.

This `NeuronTenant` targets a Neuron Operator with cluster name set to `dev01` (that will create the tenant in `dev01-neuron-pulsar` Pulsar cluster).

This `NeuronTenant` sets a `KeepAfterDeletion` lifecycle policy (which is the default value) but this field can also be set to `CleanUpAfterDeletion`. The difference is visible when the resource is deleted from a Cortex cluster, if set to `CleanUpAfterDeletion` the Neuron Operator will attempt to delete the tenant from its Pulsar cluster as well, otherwise it will keep the tenant in Pulsar and simply unblock the deletion of the Cortex resource.

The `settings` field maps directly to settings that you can send to the Pulsar admin API. In short `allowedClusters` is a list of clusters that this tenant is allowed to be replicated to and `adminRoles` is a list of Pulsar roles that will be admins of this tenant.

### 2. NeuronNamespace

Now that a tenant exists in Pulsar, a namespace can be created next. This can be done with the `NeuronNamespace` resource.

```yaml
apiVersion: neuron.isf/v1alpha1
kind: NeuronNamespace
metadata:
  name: my-namespace
spec:
  tenant: rbi
  namespace: transactions
  neuronClusterName: dev01
  policies:
    retentionPolicies:
      retentionSizeInMB: 2048
      retentionTimeInMinutes: 4800
    schemaCompatibilityStrategy: FORWARD_TRANSITIVE
```

> The `lifecyclePolicy` policy field has been omitted for brewity. The same options apply as in `NeuronTenant`.

As with `NeuronTenant` the Cortex resource name and the Pulsar namespace name is decoupled (using the `spec.namespace` field).

In Pulsar every namespace has to belong to a tenant that has been previously created in the Pulsar cluster. This is done with the `spec.tenant` field.

The `neuronClusterName` is again set to `dev01` to target the same Pulsar cluster.

Finally the `policies` field sets all the namespace policies. This is a direct mapping to the policies in the Pulsar admin API (see [here](https://Pulsar.apache.org/admin-rest-api/#operation/createNamespace)) with the exception that all fields written in snake_case have been converted to camelCase. The operator makes sure that all the policies defined in the resource are set in the Pulsar cluster.

### 3. NeuronTopic

After a tenant and namespace have been created, the next thing is to create a topic. This is done with the `NeuronTopic` resource.

```yaml
apiVersion: neuron.isf/v1alpha1
kind: NeuronTopic
metadata:
  name: my-topic
spec:
  tenant: rbi
  namespace: transactions
  topic: transactions-in-group-currency-v1
  neuronClusterName: dev01
  partitions: 8
  persistent: true
  policies:
    deduplicationEnabled: true
    inactiveTopicPolicies:
      deleteWhileInactive: false
    messageTtlInSeconds: 3600
```

> The `lifecyclePolicy` policy field has been omitted for brewity. The same options apply as in `NeuronTenant`.

As with previous resources the name of the Cortex resource is decoupled from the Pulsar topic name (with `spec.topic`).

Fields `spec.tenant` and `spec.namespace` target the Pulsar tenant and namespace, respectively.

The same Pulsar cluster (`dev01`) is again targeted with the `spec.neuronClusterName` field.

The number of partitions and persistence of the topic is set with `spec.partitions` and `spec.persistent` fields, respectively.

Topic level policies can be set using the `spec.policies` field. Do note that topic level policies [need to be explicitly enabled](https://streamnative.io/en/blog/release/2020-12-25-pulsar-270/) in order for this to work. Only a subset of options available in Pulsar namespaces are available in topics and the exhaustive list isn't available in Pulsar documentation so to see what's supported run `kubectl explain neurontopics.spec.policies`, look at the API explorer in Cortex console or read the CRD [here](https://code.rbi.tech/raiffeisen/neuron-operator-application/blob/main/crds/neurontopic.yaml).

> Note: Pulsar removes dormant topics by default. If you deploy a topic make sure that there are active consumers on the topic or configure a retention policy on namespace- / topic-level. Otherwise Pulsar will remove the topic and the operator will recreate it in a endless loop.

### 4. NeuronSchema

The final resource to create is then schemas. As with other resources it needs to target existing resources, being tenant, namespace and topic.

```yaml
apiVersion: neuron.isf/v1alpha1
kind: NeuronSchema
metadata:
  name: my-schema
spec:
  tenant: rbi
  namespace: transactions
  topic: transactions-in-group-currency-v1
  neuronClusterName: dev01
  type: AVRO
  schema:
    name: NeuronDemoTransaction
    type: record
    doc: Transaction for neuron demo application
    fields:
      - name: bic
        type: string
      - name: countryOfBirth
        type: string
      - name: customerId
        type: string
      - name: dateOfBirth
        type: string
      - name: dateOfOpened
        type: string
      - name: firstName
        type: string
      - name: lastName
        type: string
      - name: lineOfBusiness
        type: string
      - name: placeOfBirth
        type: string
      - name: title
        type:
          - 'null'
          - string
  properties:
    owner: ATG
    email: atg@email.com
```

> The `lifecyclePolicy` policy field has been omitted for brewity. The same options apply as in `NeuronTenant`.

Not to beat a dead horse, but Cortex resource name and Pulsar schema name are decoupled (see `spec.topic`).

This is again deployed to Pulsar cluster `dev01` with `spec.neuronClusterName`.

This schema is of type `AVRO` but can also be `JSON`. Do note though that `spec.schema` should still be specified as an Avro schema and not a JSON schema.

The `spec.schema` field specifies the schema definition that should be deployed, always in Avro schema format.

Finally `spec.properties` is an arbitrary string key-value map that can be added to the Pulsar schema for documentation.

> Note: Pulsar removes dormant topics by default. If you deploy a schema make sure that there are active consumers on the topic or configure a retention policy on namespace- / topic-level. Otherwise schema deployment will fail with error "Topic not found."

### Note on role permissions on resources

In the Pulsar API role permissions are set in the Namespace policies.

**Example:**

```bash
GET /admin/v2/namespaces/my-tenant/my-namespace

{
  "auth_policies": {
    "namespace_auth": {
      "MY-PRODUCER": [
        "produce"
      ],
      "MY-CONSUMER": [
        "consume"
      ]
    },
    "destination_auth": {
      "persistent://my-tenant/my-namespace/my-topic": {
        "MY-APP-ROLE": [
          "consume",
          "produce"
        ]
      }
    }
  }
  ...
}
```

Here the roles `MY-PRODUCER` and `MY-CONSUMER` can produce and consume, respectively, on any topic in the namespace. However the role `MY-APP-ROLE` can consume and produce on only the persistent topic `my-tenant/my-namespace/my-topic`.

From a usability standpoint this isn't a nice way of handling topic level permissions (having to list them all in the namespace resource) so instead `NeuronNamespace` and `NeuronTopic` resources have `spec.rolePermissions` field to be able to handle these on each level.

**Example:**
```yaml
apiVersion: neuron.isf/v1alpha1
kind: NeuronNamespace
metadata:
  name: my-namespace
spec:
  tenant: my-tenant
  namespace: my-namespace
  neuronClusterName: dev01
  rolePermissions:
    MY-PRODUCER:
      - produce
    MY-CONSUMER:
      - consume
---
apiVersion: neuron.isf/v1alpha1
kind: NeuronTopic
metadata:
  name: my-topic
spec:
  tenant: my-tenant
  namespace: my-namespace
  topic: my-topic
  neuronClusterName: dev01
  persistent: true
  rolePermissions:
    MY-APP-ROLE:
      - consume
      - produce
```

This will produce the same results.

> **Attention:** Topic level permissions _can not_ remove permissions added on the namespace level, only add new ones.

## Contributing

See [code generation docs](docs/code-generation.md).
