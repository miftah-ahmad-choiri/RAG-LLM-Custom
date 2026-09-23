# Compatibility matrix

> **Index:** `3`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=compatibility-matrix](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=compatibility-matrix)

---

## Compatibility matrix for IBM Storage Ceph 9.9.1

Last Updated
: 2026-09-06

Use this information for products supported by IBM Storage Ceph 9.9.1.

The following tables list supported compatibility with
IBM Storage Ceph
9.9.1
.

- Supported host operating system
- Supported products
- Analytics and AI
- Supported products for IBM Storage Ceph as a backup target
- Independent software vendors
- External key managers
- Supported identity providers (SSO)
- Supported S3 endpoints for Object Storage policy based archive and retrieval

| Host operating system | Version | Notes |
| --- | --- | --- |
| Red Hat Enterprise Linux (RHEL) | 9.8 10.2 | Standard lifecycle RHEL is included in the product. FIPS mode is supported. For more information and access to FIPS builds, contact your IBM representative. |

Use Ceph client packages included with any currently supported Red Hat Enterprise Linux distribution. IBM and Red Hat support RHEL clients as part of the product subscription. Third party drivers can be utilized with the IBM Storage Ceph cluster, with client support from their respective vendor. Ideally, the Ceph client packages should correspond with the Ceph release that is deployed in the Ceph cluster that the client needs to connect to.

> 📝 **Note:** Important:
All nodes in the cluster and their clients must use the supported OS version(s) to ensure that the version of the
`ceph`
package is the same on all nodes. Using different versions of the
`ceph`
package is not supported.

| Product | Version | Notes |
| --- | --- | --- |
| Ansible | Supported in a limited capacity. | Supported for upgrade and conversion tocephadm and for other minimal playbooks. |
| IBM Storage Ceph Plugin for vSphere | 1.4.0 | For more information, see IBM Storage Ceph Plugin for vSphere documentation. |
| IBM Storage Ceph CSI driver | 9.9.1 | For more information, see IBM Storage Ceph CSI driver documentation. |
| IBM Storage Ceph S3 Object Browser | 1.0.0 | For more information, see IBM Storage Ceph S3 Object Browser documentation. |
| IBM Storage Ceph Storage Replication Adapter | 1.1.0 | For more information, see IBM Storage Ceph Storage Replication Adapter documentation. |
| IBM Storage Ceph Multi-Cluster Manager | 1.1.0 | For more information, see IBM Storage Ceph Storage Multi-Cluster Manager documentation. |
| Red Hat OpenShift Data Foundation | See the Red Hat OpenShift Data Foundation Supportability and Interoperability Checker for detailed external mode version compatibility. | None |
| Red Hat Satellite | 6.x | Only registering with the Content Delivery Network (CDN) is supported. Registering with Red Hat Network (RHN) is deprecated and not supported. |
| VMware consuming Storage from Ceph | N/A | IBM Storage Ceph is certified to provide storage for VMware with the NVMe/TCP protocol. Support is available for VMware ESXi version 7.0U3 and later. Use IBM Storage Ceph Plugin for vSphere to manage Ceph NVMe/TCP block storage through vCenter. For more information, see IBM Storage Ceph Plugin for vSphere documentation. For more information about hardware requirements, see Minimum hardware requirements. For more information, see the VMware Compatibility Guide for Ceph NVMe-oF Gateway and vSphere Client Plug In. |
| Ceph deployed on VMware | N/A | IBM Storage Ceph supports deployments on the VMware hypervisor. Use the same CPU core and RAM requirements for VM sizing as for baremetal deployments. For production deployments: It is not recommended to deploy virtualized Ceph on SDS-based storage, such as vSAN. Direct storage access (RDM) must be provided to the VMs that are running the Ceph components. Core Ceph redundant services (MONs, MGRs, and OSDs) must be deployed on physically different hypervisor hosts to avoid a single-point of failure (SPOF). For example, do not run all three Ceph MONs on the same hypervisor host. |

| Client connector | Version | Notes |
| --- | --- | --- |
| Apache Ranger RAZ (Ranger Authorized Proxy) | CDP Private Cloud Base 7.3.1 | S3-compatible datasource via Hadoop S3A. Kerberos/SPNEGO authentication with Ranger policy enforcement. Static S3 credentials are supported. STS AssumeRole is not supported. Virtual-hosted-style S3 access is required. |
| Cloudera Data Platform (CDP) Private Cloud Base – Ranger RAZ | 7.3.1 | S3-compatible datasource via Ranger RAZ (Ranger Authorized Proxy). Validated with static S3 credentials. Virtual-hosted-style S3 access is required. |
| Dremio | 25.2 or later | S3-compatible datasource |
| Hadoop S3A | 2.8.x, 3.2.x, and trunk | None |
| IBM watsonx.data | 1.0.3 or later | None |
| Polaris Catalog | 0.9.0 or later | S3_COMPATIBLE allows Credential Vending (IAM/STS) |
| Snowflake | N/A | SaaS Cloud service |
| Splunk SmartStore | 9.2.1 or later | None |
| Starburst Enterprise | N/A | SaaS Cloud service |
| Weka Data Platform | 3.12.2 | None |

| IBM Storage Ceph as a backup target | Version | Notes |
| --- | --- | --- |
| Cohesity DataProtect | 7.1.2_u1 or later | S3 Cloud Archive, Object Lock, Versioning |
| CommVault Platform | v11.20 or later | S3 target |
| FalconStor StorSafe Server | 11.11 or later | S3 target and Dedupe Data Repository |
| IBM Fusion Backup & Restore | 2.6 and 2.7 | S3 target |
| IBM Storage Defender Data Protect | 7.1.2_u1 or later | S3 Cloud Archive, Object Lock, Versioning |
| IBM Storage Protect | 8.1.18 | S3 target (Object Lock) |
| NetApp AltaVault | 4.3.2 and 4.4 | None |
| Rubrik Cloud Data Management (CDM) | 3.2 or later | None |
| Trilio, TrilioVault | 3.0 | S3 target |
| Veeam (object storage) | Repository Primary Target Veeam v12 Repository Capacity Target with Immutability Veeam v12 | Supported on IBM Storage Ceph object storage with the S3 protocol |
| Veritas NetBackup Cloud Storage | 10.x or later | S3 target |

| Independent software vendors | Version | Notes |
| --- | --- | --- |
| CTERA | 8.x | CTERA Direct IO. Verified compatibility with IBM Storage Ceph for direct replication of objects from CTERA Edge Filers using S3 Pre-Signed URLs. CTERA Vault. Support for write-once, read-many (WORM) volumes with IBM Storage Ceph using S3 Object Lock. Objects are retained according to the defined retention policies configured in CTERA Vault. |
| FalconStor StorGuard | 9 | None |
| IBM FileNet Content Manager | 5.5.9 or later | None |
| IBM Fusion Data Catalog | 2.0.3 | None |
| IBM Security Verify | N/A | SaaS Cloud service |
| IBM Storage Scale AFM to Cloud Object Storage | 5.1.9.0 | For more information, seeConfiguring > Configuring AFM to cloud object storage within theIBM Storage Scale documentation. |
| IBM TS7700C (Cloud) | 8.60.0.115 | S3 target Cloud-Attach configuration only (feature code 5278) Requires EXEC 402 1.02 or later |
| IBM z/OS | 3.1 or later | S3 target through DFSMSdfp CDA |
| Komprise Intelligent Data Management | 6.3.0 or later | None |

| External key manager | Version | Notes |
| --- | --- | --- |
| Hashicorp Vault | 1.12 or later | SSE-KMS, SSE-S3 |
| IBM Security Key Lifecycle Manager (GKLM/SKLM) | 5.1 | SSE-KMS |
| Thales CipherTrust | 2.8 | SSE-KMS |

| Supported identity providers | Version | Notes |
| --- | --- | --- |
| IBM Cloud Identity and Access Management (IAM) | N/A | SaaS cloud service, Object STS/OIDC auth |
| IBM Security Verify | N/A | SaaS Cloud service |
| Keycloak | 22.0 or later | Dashboard SSO, Object STS/OIDC auth |
| Red Hat Build of Keycloak (RHBK) | 26.2 or later | Dashboard SSO, Object STS/OIDC auth |
| Red Hat Single Sign On | 7.6.0 or later | Dashboard SSO, Object STS/OIDC auth |

| S3 endpoint | Version | Notes |
| --- | --- | --- |
| AWS S3 Glacier Storage Classes | N/A | S3 Glacier API |
| AWS S3 Standard Storage Classes | N/A | S3 API |
| IBM Cloud Object Storage (COS) Standard Storage Class | N/A | S3 API |
| IBM Cloud Object Storage (COS) Accelerated Archive Storage Class | N/A | S3 Glacier API |
| IBM Storage Deep Archive | 1.1.0 or later | S3 Glacier API (validated with 3 million objects per storage class) |
| IBM Storage Ceph | 7.1 or later | S3 API |
| PoINT Archival Gateway (Tape) | 4.1 or later | S3 API |

For more information, see Policy based data archival and retrieval to S3 compatible platforms.

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=compatibility-matrix](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=compatibility-matrix)*