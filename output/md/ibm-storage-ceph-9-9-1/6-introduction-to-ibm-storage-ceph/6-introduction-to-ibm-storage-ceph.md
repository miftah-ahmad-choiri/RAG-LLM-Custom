# Introduction to IBM Storage Ceph

> **Index:** `6`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=introduction-storage-ceph](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=introduction-storage-ceph)

---

## Introduction to IBM Storage Ceph

Last Updated
: 2026-06-25

IBM Storage Ceph cluster is a distributed data object store designed to provide excellent performance, reliability and scalability.

IBM Storage Ceph is a scalable, open, software-defined storage platform that combines an enterprise-hardened version of the Ceph storage system, with a Ceph management platform, deployment utilities, and support services. IBM Storage Ceph is designed for cloud infrastructure and web-scale object storage.

Distributed object stores are the future of storage, because they accommodate unstructured data, and because clients can use modern object interfaces and legacy interfaces simultaneously.

For example:

- APIs in many languages (C/C++, Java, Python)
- RESTful interfaces (S3/Swift)
- Block device interface
- File system interface

The power of IBM Storage Ceph cluster can transform your organization’s IT infrastructure and your ability to manage vast amounts of data, especially for cloud computing platforms like Red Hat Enterprise Linux OSP. The cluster delivers extraordinary scalability–thousands of clients accessing petabytes to exabytes of data and beyond.

IBM Storage Ceph can be utilized with IBM watsonx.data to create a data lakehouse that is optimized by IBM watsonx.data for data, analytics, and AI applications. IBM watsonx.data provides a single point of entry to all its data and enables rapid access to storage and analytics environments for advanced query engines. For more information, see the IBM Storage Ceph for IBM watsonx.data chapter, within the [IBM Storage Ceph Solutions Guide](https://www.redbooks.ibm.com/abstracts/redp5715.html) Redpaper publication.

At the heart of every Ceph deployment is the IBM Storage Ceph cluster. It consists of three types of daemons:

Ceph OSD Daemon
Ceph OSDs store data on behalf of Ceph clients. Additionally, Ceph OSDs utilize the CPU, memory and networking of Ceph nodes to perform data replication, erasure coding, rebalancing, recovery, monitoring and reporting functions.
Ceph Monitor
A Ceph Monitor maintains a master copy of the
IBM Storage Ceph
cluster map with the current state of the cluster. Monitors require high consistency, and use Paxos to ensure agreement about the state of the cluster.
Ceph Manager
The Ceph Manager maintains detailed information about placement groups, process metadata and host metadata in lieu of the Ceph Monitor—significantly improving performance at scale. The Ceph Manager handles execution of many of the read-only Ceph CLI queries, such as placement group statistics. The Ceph Manager also provides the RESTful monitoring APIs.
Figure 1.
Daemons

Ceph client interfaces read data from and write data to the IBM Storage Ceph cluster. Clients need the following data to communicate with the IBM Storage Ceph cluster:

- The Ceph configuration file, or the cluster name (usually `ceph`) and the monitor address.
- The pool name.
- The user name and the path to the secret key.

Ceph clients maintain object IDs and the pool names where they store the objects. However, they do not need to maintain an object-to-OSD index or communicate with a centralized object index to look up object locations. Then, Ceph clients provide an object name and pool name to `librados`, which computes an object’s placement group and the primary OSD for storing and retrieving data using the CRUSH (Controlled Replication Under Scalable Hashing) algorithm. The Ceph client connects to the primary OSD where it may perform read and write operations. There is no intermediary server, broker or bus between the client and the OSD.

When an OSD stores data, it receives data from a Ceph client, whether the client is a Ceph Block Device, a Ceph Object Gateway, a Ceph File System or another interface and it stores the data as an object.

> 📝 **Note:** Note:
An object ID is unique across the entire cluster, not just an OSD’s storage media.

Ceph OSDs store all data as objects in a flat namespace. There are no hierarchies of directories. An object has a cluster-wide unique identifier, binary data, and metadata consisting of a set of name/value pairs.

Figure 2.
Object

Ceph clients define the semantics for the client’s data format. For example, the Ceph Block Device maps a block device image to a series of objects stored across the cluster.

> 📝 **Note:** Note:
Objects consisting of a unique ID, data, and name/value paired metadata can represent both structured and unstructured data, as well as legacy and leading edge data storage interfaces.

IBM Storage Ceph
clusters consist of the following types of nodes:
Ceph Monitor
Each Ceph Monitor node runs the
`ceph-mon`
daemon, which maintains a primary copy of the storage cluster map. The storage cluster map includes the storage cluster topology. A client connecting to the Ceph storage cluster retrieves the current copy of the storage cluster map from the Ceph Monitor, enabling the client to read from and write data to the storage cluster.

> 📝 **Note:** Important:
The storage cluster can run with just one Ceph Monitor; however, to ensure high availability in a production storage cluster,
IBM
supports deployments with at least three Ceph Monitor nodes. Deploy a total of 5 Ceph Monitors for storage clusters exceeding 750 Ceph OSDs.

Ceph Manager
The Ceph Manager daemon,
`ceph-mgr`
, co-exists with the Ceph Monitor daemons running on Ceph Monitor nodes to provide extra services. The Ceph Manager provides an interface for other monitoring and management systems using Ceph Manager modules. Running the Ceph Manager daemons is a requirement for normal storage cluster operations.
Ceph OSD
Each Ceph Object Storage Device (OSD) node runs the
`ceph-osd`
daemon, which interacts with logical disks that are attached to the node. The storage cluster stores data on these Ceph OSD nodes.

Ceph can run with few OSD nodes, of which the default is three, but production storage clusters realize better performance beginning at modest scales. For example, 50 Ceph OSDs in a storage cluster. Ideally, a Ceph storage cluster has multiple OSD nodes, allowing for the possibility to isolate failure domains by configuring the CRUSH map.

Ceph MDS
Each Ceph Metadata Server (MDS) node runs the
`ceph-mds`
daemon, which manages metadata related to files stored on the Ceph File System (CephFS). The Ceph MDS daemon also coordinates access to the shared storage cluster.
Ceph Object Gateway
Ceph Object Gateway node runs the
`ceph-radosgw`
daemon, and is an object storage interface built on top of
`librados`
to provide applications with a RESTful access point to the Ceph storage cluster. The Ceph Object Gateway supports two interfaces:
S3
Provides object storage functionality with an interface that is compatible with a large subset of the Amazon S3 RESTful API.
Swift
Provides object storage functionality with an interface that is compatible with a large subset of the OpenStack Swift API.

> 📝 **Note:** Note:

- For more information about Ceph architecture, see Architecture.
- For the minimum hardware recommendations, see Hardware.

For more information, see the IBM Storage Ceph main features and capabilities chapter, within the IBM Storage Ceph Concepts and Architecture Guide [Redpaper](https://www.redbooks.ibm.com/abstracts/redp5721.html) publication.

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=introduction-storage-ceph](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=introduction-storage-ceph)*