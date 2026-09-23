# Ceph NVMe-oF gateway

> **Index:** `23`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-nvme-gateway](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-nvme-gateway)

---

## Ceph NVMe-oF gateway

Last Updated
: 2026-09-09

Storage administrators can install and configure an NVMe over Fabrics (NVMe-oF) gateway for an IBM Storage Ceph cluster. With Ceph NVMe-oF gateways, you can effectively run a fully integrated block storage infrastructure with all features and benefits of a conventional Storage Area Network (SAN).

> 📝 **Note:** Note:

- The NVMe-oF gateway supports VMware vSphere APIs (VAAI), which includes support for vMotion, compare and write, unmap, and write zero.
- NVMe reserve is supported for host clustering.

Block-level access to a Ceph storage cluster used to be limited to QEMU and `librbd`. Block-level access to the Ceph storage cluster can now take advantage of the NVMe-oF standard to provide data storage.

Use the Ceph Dashboard to easily configure and manage the Ceph NVMe-oF gateway. For more information, see Managing the Ceph NVMe-oF gateway.

The NVMe-oF gateway integrates IBM Storage Ceph with the NVMe over TCP (NVMe/TCP) protocol to provide an NVMe/TCP target that exports Ceph Block Device (RBD) images. The NVMe/TCP protocol allows clients, which are known as initiators, to send NVMe-oF commands to storage devices, which are known as targets, over an Internet Protocol network. Initiators can be Linux clients, VMware clients, or both. For VMware clients, the NVMe/TCP volumes are shown as VMFS Datastore and for Linux clients, the NVMe/TCP volumes are shown as block devices.

Figure 1.
Ceph NVMe-oF gateway

For more information about the NVMe over Fabrics (NVMe-oF) protocol, see NVMe over Fabrics.

### NVMe-oF in a stretch cluster

An NVMe-oF stretch cluster extends an IBM Storage Ceph deployment across two sites to provide continuous NVMe-over-Fabrics block storage access during site-level failures and planned workload movement.

In a stretch cluster configuration, Ceph storage nodes and NVMe-oF gateways are distributed across two sites, commonly referred to as Site A and Site B. The sites are connected by a network with controlled latency, typically in the range of 2–10 milliseconds.

NVMe-oF initiators, such as VMware ESXi hosts, access Ceph Block Device (RBD) storage through NVMe-oF gateways deployed in both sites. The stretch cluster architecture is designed to support business continuity and disaster recovery (BCDR) use cases, including infrastructure failures, planned maintenance, and controlled migration of workloads between sites.

For more information about stretch cluster behavior, supported architectures, and failure scenarios, see NVMe-oF in a stretch cluster.

For general information about using IBM Storage Ceph stretch clusters, see Stretch clusters for Ceph storage.

### High Availability with NVMe-oF gateway group

High Availability (HA) provides I/O and control path redundancies for the host initiators. High Availability is also sometimes referred to as failover and failback support. The redundancy that HA creates is critical to protect against one or more gateway failures. With HA, the host can continue the I/O with only the possibility of performance latency until the failed gateways are back and functioning correctly.

NVMe-oF gateways are virtually grouped into
gateway groups
and the HA domain sits within the gateway group. An NVMe-oF gateway group supports eight gateways. Each NVMe-oF gateway in the gateway group can be used as a path to any of the subsystems or namespaces that are defined in that gateway group. HA is effective with two or more gateways in a gateway group.

> 📝 **Note:** Important:
An NVMe-oF gateway can only be part of one gateway group and should never be part of two or more gateway groups.

High Availability is enabled by default. To use High Availability, a minimum of two gateways and listeners must be defined. For more information, see Deploying the NVMe-oF gateway.

It is important to create redundancy between the host and the gateways. To create a fully redundant network connectivity, be sure that the host has two Ethernet ports that are connected to the gateways over a network with redundancy (for example, two network switches).

The HA feature uses the Active/Standby approach for each namespace. Using Active/Standby means that at any point in time, only one of the NVMe-oF gateways serve I/O from the host to a specific namespace. To properly use all NVMe-oF gateways, each namespace is assigned to a different load-balancing group. The number of load-balancing groups is equal to the number of NVMe-oF gateways in the gateway group.

With HA, if an NVMe-oF gateway fails, the initiator continues trying to connect. The amount of time that it tries to connect for depends on what is defined for the initiator. For more information about defining the reconnect time for the initiator and general configuration instructions, see Configuring the NVMe-oF gateway initiator.

### Scaling-out with NVMe-oF gateway

The NVMe-oF gateway supports
scale-out
.
NVMe-oF gateway scale-out
supports:

- Up to 4 NVMe-oF gateway groups.
- Up to 8 NVMe-oF gateways in a gateway group.
- Up to 128 NVMe-oF subsystems within a gateway group.
- Up to 512 hosts per gateway group.

> 📝 **Note:** Note:
If more than 512 host are required, contact
[IBM Support](https://www.ibm.com/mysupport/)
.
- 4096 namespaces per gateway group.

> 📝 **Note:** Important:
An NVMe-oF gateway can only be part of one gateway group and should never be part of two or more gateway groups.

> 📝 **Note:** Note:
The RHEL and ESXi initiators can have smaller NVMe over Fabric namespace discovery limits. Confirm all discovery limits with your software vendor and version.

### NVMe Discovery

The IBM Storage Ceph NVMe-oF gateway supports NVMe Discovery. Each gateway instance that runs in the Ceph cluster also runs a Discovery Controller, which reports the IP addresses of all gateways in the group that are configured with listeners.

For configuring information, see Configuring the NVMe-oF gateway initiator.

### NVMe-oF gateway in-band authentication

> 📝 **Note:** Important:
In-band authentication is supported on an initiator with Red Hat Enterprise Linux 9.5 or later. ESX is not supported.

> 📝 **Note:** Note:
DH-HMAC-CHAP authentication requires Linux kernel version 6.0.0 or later. Earlier kernel versions, such as Ubuntu 5.15.0-82-generic do not support the required
dhchap_secret
option.

The Ceph NVMe-oF gateway uses in-band authentication to maintain security against unknown connection requests from unknown initiators. Using the in-band authentication helps ensure appropriate subsystem access only from authorized hosts. NVMe-oF gateway uses SPDK for DH-HMAC-CHAP authentication, allowing users to authenticate with either unidirectional or bidirectional modes.

Table 1 breaks down the two authentication mode types. The difference between unidirectional and bidirectional authentication is if the subsystem has a key. If only the host contains the DH-HMAC-CHAP key, and the subsystem does not, unidirectional authentication is used.

In cases where the subsystem has a key all hosts that are added to the subsystem must also have a key.

> 📝 **Note:** Important:
Adding a host without a key to a subsystem that contains a key causes failure when running the
host add
command.

Key values are stored encrypted. To use DH-HMAC-CHAP authentication keys, you must create an encryption key. For more information about creating an encryption key, see
Defining an NVMe-oF subsystem with nvmeof-cli
.

| Authentication mode type | Description | Direction |
| --- | --- | --- |
| Unidirectional | Target verifies the host | Initiator to target |
| Bidirectional | Target verifies the host Host verifies the target | Initiator to target Target to initiator |

The Ceph NVMe‑oF gateway supports in‑band authentication by using DH‑HMAC‑CHAP to control access between NVMe initiator hosts and NVMe‑oF subsystems. Authentication keys can be configured at different scopes to support deployments that require unique authentication per host connection. For more information, see NVMe‑oF in‑band authentication.

### Using Ceph NVMe-oF gateway

Figure 2
illustrates the basic flow of using Ceph NVMe-oF gateway with the command-line interface. For full in-depth information and commands for each step, follow the procedures in the following sections or open the image in a new tab and click the steps for direct links to the relevant topics.
Figure 2.
Ceph NVMe-oF gateway workflow with CLI

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-nvme-gateway](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-nvme-gateway)*