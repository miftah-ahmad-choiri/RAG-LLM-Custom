# Ceph File Systems

> **Index:** `20`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-file-systems](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-file-systems)

---

## Ceph File Systems

Last Updated
: 2026-06-25

As a storage administrator, you can configure the Ceph Metadata Server (MDS) and how to create, mount, and work the Ceph File System (CephFS). Get to know the features, system components, and limitations to manage a CephFS environment.

The Ceph File System (CephFS) is a file system compatible with POSIX standards that is built on top of the Ceph distributed object store, RADOS (Reliable Autonomic Distributed Object Storage). CephFS provides file access to an IBM Storage Ceph cluster, and uses the POSIX semantics wherever possible. For example, in contrast to many other common network file systemslike NFS, CephFS maintains strong cache coherency across clients. The goal is for processes that use the file system to behave the same when they are on different hosts as when they are on the same host. However, sometimes CephFS diverges from the strict POSIX semantics.

The Ceph File System has the following features:
Parallel data streams
CephFS is a parallel file system. Clients and storage servers can exchange data through multiple-streams in parallel, which helps increase throughput and scalability.
Scalability
The Ceph File System is highly scalable due to horizontal scaling of metadata servers and direct client reads and writes with individual OSD nodes.
Shared file system
The Ceph File System is a shared file system so multiple clients can work on the same file system simultaneously.
Multiple file systems
You can have multiple file systems active on one storage cluster. Each CephFS has its own set of pools and its own set of Metadata Server (MDS) ranks. When deploying multiple file systems this requires more running MDS daemons. This can increase metadata throughput, but also increases operational costs. You can also limit client access to certain file systems.
High availability
The Ceph File System provides a cluster of Ceph Metadata Servers (MDS). One is active and others are in standby mode. If the active MDS stops unexpectedly, one of the standby MDS becomes active. As a result, client mounts continue working through a server failure. This behavior makes the Ceph File System highly available. In addition, you can configure multiple active metadata servers.
Configurable file and directory layouts
The Ceph File System allows users to configure file and directory layouts to use multiple pools, pool namespaces, and file striping modes across objects.
POSIX Access Control Lists (ACL)
The Ceph File System supports the POSIX Access Control Lists (ACL). ACLs are enabled by default with the Ceph File Systems mounted as kernel clients with kernel version
`kernel-3.10.0-327.18.2.el7`
or newer. To use an ACL with the Ceph File Systems mounted as FUSE clients, you must enable them.
Client quotas
The Ceph File System supports setting quotas on any directory in a system. The quota can restrict the number of bytes or the number of files that are stored beneath that point in the directory hierarchy. CephFS client quotas are enabled by default.

- For more information about installing Ceph Metadata servers, see Managing the MDS service.
- For more information about creating Ceph File Systems, see Deploying the CephFS.

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-file-systems](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-file-systems)*