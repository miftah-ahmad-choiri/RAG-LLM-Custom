# Ceph Block Devices and OpenStack

> **Index:** `22`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices-openstack](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices-openstack)

---

## Ceph Block Devices and OpenStack

Last Updated
: 2026-06-25

IBM Storage Ceph integration with Red Hat OpenStack provides scalable and resilient block storage for cloud workloads, supporting virtual machine images, volumes, and guest disks.

IBM Storage Ceph integrates with OpenStack distributed block storage backend that scales horizontally and delivers high availability for cloud workloads. In an integrated environment, Ceph Block Devices are consumed by multiple OpenStack services, to store and manage images, volumes, persistent and virtual machine disks efficiently.

This section describes the supported integration models between Ceph and OpenStack, the OpenStack services that can use Ceph block storage, and key considerations to review before configuring the environment.

For detailed deployment guidance and service‑specific configuration options, see the [Red Hat OpenStack Platform](https://www.ibm.com/links?url=https%3A%2F%2Faccess.redhat.com%2Fdocumentation%2Fen-us%2Fred_hat_openstack_platform%2F) documentation for your specific OpenStack release.

### Ceph and OpenStack integration models

OpenStack can use Ceph Block Devices in the following deployment models:

OpenStack‑managed Ceph cluster
In this model, OpenStack creates and manages the Ceph storage cluster as part of the deployment. OpenStack installs and configures Ceph components, including monitors and object storage daemons (OSDs). This approach simplifies deployment by allowing OpenStack to automate Ceph installation and configuration.
Existing Ceph cluster integration
OpenStack connects to a preconfigured Ceph storage cluster and uses existing Ceph monitors. Ceph block devices are configured as a storage backend for OpenStack services. This model is typically used when a Ceph cluster already exists or when storage and cloud infrastructure are managed separately.

> 📝 **Note:** Note:
The procedures described in this guide assume that you are manually configuring OpenStack to use an existing Ceph cluster rather than using automated deployment tools such as an OpenStack director.

### OpenStack services that use Ceph Block Devices

Ceph Block Devices can be used as storage backends for several OpenStack services:

Image storage (Glance)
OpenStack Glance manages virtual machine images, which are treated as immutable objects. When Glance is configured to use Ceph, images are stored in a Ceph Block Device pool and can be efficiently cloned using copy-on-write mechanisms.
Volume storage (Cinder and Cinder Backup)
OpenStack Cinder provides persistent block storage volumes that can be attached to running virtual machines, used for boot-from-volume instances, or backed up using Cinder Backup. Ceph can be used as a backend for both Cinder volumes and Cinder Backup storage.
Guest virtual machine disks (Nova)
Ceph block devices can store guest virtual machine disks directly. Instead of maintaining disk files on the hypervisor file system, Nova accesses disks from Ceph, improving scalability and enabling features such as live migration.

### Image format and storage considerations

Ceph does not support the QCOW2 image format for hosting virtual machine disks. To boot virtual machines using Ceph block storage, images configured in Glance must use the RAW format.

This requirement applies to both ephemeral disks and boot‑from‑volume instances.

OpenStack can use Ceph for any combination of image storage, volume storage, or guest disk storage. There is no requirement to use Ceph for all three services.

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices-openstack](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices-openstack)*