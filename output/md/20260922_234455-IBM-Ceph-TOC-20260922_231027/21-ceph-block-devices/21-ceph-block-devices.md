# Ceph Block Devices

> **Index:** `21`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices)

---

## Ceph Block Devices

Last Updated
: 2026-06-25

Learn to manage, create, configure, and use IBM Storage Ceph Block Devices.

A block is a set length of bytes in a sequence, for example, a 512-byte block of data. Combining many blocks together into a single file can be used as a storage device that you can read from and write to. Block-based storage interfaces are the most common way to store data with rotating media such as:

- Hard drives
- CD/DVD discs
- Floppy disks
- Traditional 9-track tapes

Ceph Block Devices are thin-provisioned, resizable and store data striped over multiple Object Storage Devices (OSD) in a Ceph storage cluster. Ceph Block Devices are also known as Reliable Autonomic Distributed Object Store (RADOS) Block Devices (RBDs). Ceph Block Devices leverage RADOS capabilities such as:

- Snapshots
- Replication
- Data consistency

Ceph Block Devices interact with OSDs by using the `librbd` library.

Ceph Block Devices deliver high performance with infinite scalability to Kernel Virtual Machines (KVMs), such as Quick Emulator (QEMU), and cloud-based computing systems, like OpenStack, that rely on the
`libvirt`
and QEMU utilities to integrate with Ceph Block Devices. You can use the same storage cluster to operate the Ceph Object Gateway and Ceph Block Devices simultaneously.

> 📝 **Note:** Important:
Using Ceph Block Devices requires access to a running Ceph storage cluster. For more information about installing
an
IBM Storage Ceph
cluster, see
Initial installation
.

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-block-devices)*