# Edge clusters

> **Index:** `15`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=edge-clusters](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=edge-clusters)

---

## Edge clusters

Last Updated
: 2026-06-25

Edge clusters are a solution for cost-efficient object storage configurations.

IBM
supports the following minimum configuration of
an
IBM Storage Ceph
cluster:

- A three node cluster with two replicas for SSDs.
- A four-node cluster with three replicas for HDDs.
- A four-node cluster with EC pool with 2+2 configuration.
- A four-node cluster with 8+6 CRUSH MSR configuration.

With smaller clusters, the utilization goes down because of the amount of usage and the loss of resiliency.

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=edge-clusters](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=edge-clusters)*