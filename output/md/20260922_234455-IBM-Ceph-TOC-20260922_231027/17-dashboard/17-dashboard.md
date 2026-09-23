# Dashboard

> **Index:** `17`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=dashboard](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=dashboard)

---

## Dashboard

Last Updated
: 2026-07-23

As a storage administrator, the IBM Storage Ceph Dashboard provides management and monitoring capabilities. Use the dashboard to administer and configure the cluster, and visualize information and performance statistics that are related to it. The dashboard uses a web server that is hosted by the `ceph-mgr` daemon.

The dashboard is accessible from a web browser and includes many useful management and monitoring features. For example, use the dashboard to configure manager modules and monitor the state of OSDs.

> 📝 **Note:** Note:
To use the
IBM Storage Ceph
dashboard, have system administrator level experience.

The dashboard provides the following features:
Multi-user and role management
The dashboard supports multiple user accounts with different permissions and roles. User accounts and roles can be managed by using both the command line and the web user interface. The dashboard supports various methods to enhance password security. Password complexity rules can be configured, requiring users to change their password after the first login or after a configurable time period.

For more information, see Managing roles and Managing users.

Single Sign-On (SSO)
The dashboard supports authentication with an external identity provider by using the SAML 2.0 protocol.

For more information, see Enabling single sign-on with SAML 2.0.

Auditing
The dashboard backend can be configured to log all PUT, POST, and DELETE API requests in the Ceph manager log.

For more information about using the manager modules with the dashboard, see Viewing and editing the manager modules of the Ceph cluster.

High availability (Technology Preview)
Both Ceph management and Ceph monitoring uses high availability. High availability provides the users with transparent manager failover of the
`mgmt-gateway`
. High availability redirects to the active manager and to the active instance of Prometheus, Alertmanager or Grafana, when several instances are available.

> 📝 **Note:** Important:
To use high availability with the Ceph Dashboard, ensure that there are no port conflicts that might disrupt service availability. High-availability configurations and clustering for the mgmt-gateway service itself are currently not supported. Services must bind to the appropriate ports based on the applications being proxied.

### Security features

The dashboard provides the following security features.
SSL and TLS support
All HTTP communication between the web browser and the dashboard is secured through SSL. A self-signed certificate can be created with a built-in command, but it is also possible to import custom certificates that are signed and issued by a Certificate Authority (CA).

For more information, see Bootstrap storage cluster along with Dashboard.

Username and password protection
You can access the dashboard only by providing a configurable username and password.

For more information, see Managing users.

### Configuring and managing the dashboard interface

Configure and manage the Ceph Dashboard.
Configuring manager modules

You can view and change parameters for Ceph manager modules.

For more information, see Viewing and editing the manager modules of the Ceph cluster.

Embedded Grafana dashboards
Ceph Dashboard Grafana dashboards might be embedded in external applications and web pages to surface information with Prometheus modules gathering the performance metrics.

For more information, see Components.

Viewing and filtering logs
You can view event and audit cluster logs and filter them based on priority, keyword, date, or time range.

For more information, see Filtering logs of the Ceph cluster.

Toggling dashboard components
You can enable and disable dashboard components so only the features you need are available.

For more information, see Toggling Ceph dashboard features.

Quality of service for images
You can set performance limits on images. For example, limiting IOPS or read BPS burst rates.

For more information, see Managing block device images.

### Ceph management with the dashboard

Manage and monitor
IBM Storage Ceph
with the Ceph Dashboard.
Upgrading
You can upgrade the Ceph cluster version by using the dashboard.

For more information, see Upgrading a cluster.

Overall cluster health
Displays performance and capacity metrics. The cluster health also displays the overall cluster status and storage usage. For example, number of objects, raw capacity, usage per pool, a list of pools and their status and usage statistics.

For more information, see Viewing and editing the configuration of the Ceph cluster.

Configuration editor
Displays all the available configuration options, their descriptions, types, default, and currently set values. These values are editable.

For more information, see Viewing and editing the configuration of the Ceph cluster.

Managing OSD settings
You can set cluster-wide OSD flags by using the dashboard. You can also Mark OSDs up, down or out, purge and reweight OSDs, run scrub operations, modify various scrub-related configuration options, and select profiles to adjust the level of backfilling activity. You can set and change the device class of an OSD, display, and sort OSDs by device class. You can deploy OSDs on new drives and hosts.

For more information, see Managing Ceph OSDs from the Ceph Dashboard.

Pools
Lists and manages all Ceph pools and their details. For example, applications, placement groups, replication size, EC profile, quotas, and CRUSH ruleset.

For more information, see Understanding the landing page of the Ceph dashboard and Monitoring pools of the Ceph cluster.

OSDs
Lists and manages all OSDs, their status, and usage statistics.
OSDs
also lists detailed information, for example, attributes, OSD map, metadata, and performance counters for read and write operations.
OSDs
also lists all drives that are associated with an OSD.

For more information, see Monitoring Ceph OSDs.

Images
Lists all Ceph Block Device (RBD) images and their properties such as size, objects, and features. Create, copy, modify, and delete RBD images. Create, delete, and rollback snapshots of selected images, protect or unprotect these snapshots against modification. Copy or clone snapshots and flatten cloned images.

> 📝 **Note:** Note:
The performance graph for I/O changes in the
Overall Performance
tab for a specific image shows values only after specifying the pool that includes that image by setting the
rbd_stats_pool
parameter in
Cluster
>
Manager modules
>
Prometheus
.

For more information, see Monitoring block device images.

Block device mirroring
Enables and configures Ceph Block Device (RBD) mirroring to a remote Ceph server. Lists all active sync daemons and their status, pools, and RBD images including their synchronization state.

For more information, see Mirroring view.

Ceph File Systems
Lists all active Ceph File System (CephFS) clients and associated pools, including their usage statistics. Evict active CephFS clients, manage CephFS quotas and snapshots, and browse a CephFS directory structure.

For more information, see Monitoring Ceph File Systems.

Object Gateway (RGW)
Lists all active object gateways and their performance counters. This window displays and manages, including add, edit, and delete, Ceph Object Gateway users and their details. This includes quotas and users’ buckets and their details, for example, owner or quotas.

For more information, see Monitoring Ceph Object Gateway daemons.

NFS
Manages NFS shares of CephFS and Ceph Object Gateway S3 buckets by using the Ceph NFS service..

For more information, see Managing NFS shares.

Ceph NVMe-oF gateway
Manages the Ceph NVMe-oF gateway and subsystems. You can
configure NVMe-oF
services, subsystems, listeners, and namespaces. You can also add or remove an initiator NQN masking per subsystem.

For more information, see Managing the Ceph NVMe-oF gateway.

### Monitoring with the dashboard

Monitor the following components with the dashboard.
Viewing alerts
Use the alerts page to see details of current alerts.

For more information, see Viewing alerts.

Viewing cluster hierarchy
You can view the CRUSH map, for example, to determine which host a specific OSD ID is running on. This is helpful if an issue with an OSD occurs.

For more information, see Viewing the CRUSH map of the Ceph cluster.

Cluster logs
Displays and filters the latest updates to the cluster’s event and audit log files by priority, date, or keyword.

For more information, see Filtering logs of the Ceph cluster.

Centralized logs
Provides a centralized location for viewing logs in the
IBM Storage Ceph
cluster for more efficient monitoring.

For more information, see Viewing centralized logs of the Ceph cluster.

Hosts
Provides a list of all hosts that are associated with the cluster along with the running services and the installed Ceph version.

For more information, see Monitoring hosts of the Ceph cluster.

Performance counters
Displays detailed statistics for each running service.

For more information, see Monitoring services of the Ceph cluster.

Monitors
Lists all Monitors, their quorum status, and open sessions.

For more information, see Monitoring monitors of the Ceph cluster.

Device management
Lists all hosts that are known by the Orchestrator. Lists all drives that are attached to a host and their properties. Displays drive health predictions, SMART data, and blink enclosure LEDs.

For more information, see Monitoring hosts of the Ceph cluster.

View storage cluster capacity
You can view the raw storage capacity of the
IBM Storage Ceph
cluster in the Capacity pages of the Ceph dashboard.

For more information, see Understanding the landing page of the Ceph dashboard.

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=dashboard](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=dashboard)*