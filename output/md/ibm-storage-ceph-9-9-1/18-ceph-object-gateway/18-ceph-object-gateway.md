# Ceph Object Gateway

> **Index:** `18`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-object-gateway](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-object-gateway)

---

## Ceph Object Gateway

Last Updated
: 2026-07-23

Ceph Object Gateway, also known as RADOS Gateway (RGW), is an object storage interface built on top of the `librados` library to provide applications with a RESTful gateway to Ceph storage clusters. Use this information to understand how to deploy, configure, and administer a Ceph Object Gateway environment.

This uses a "Day Zero", "Day One", and "Day Two" organizational methodology, providing readers with a logical progression path.

Day Zero is where research and planning are done before implementing a potential solution.

Day One is where the actual deployment, and installation of the software happens.

Day Two is where all the basic, and advanced configuration happens.

Ceph Object Gateway supports three interfaces:
S3-compatibility
Provides object storage functionality with an interface that is compatible with a large subset of the Amazon S3 RESTful API.
Swift-compatibility
Provides object storage functionality with an interface that is compatible with a large subset of the OpenStack Swift API.

The Ceph Object Gateway is a service interacting with a Ceph storage cluster. Since it provides interfaces compatible with OpenStack Swift and Amazon S3, the Ceph Object Gateway has its own user management system. Ceph Object Gateway can store data in the same Ceph storage cluster used to store data from Ceph Block Device clients; however, it would involve separate pools and likely a different CRUSH hierarchy. The S3 and Swift APIs share a common namespace, so you can write data with one API and retrieve it with the other.

Administrative API
Provides an administrative interface for managing the Ceph Object Gateways.

Administrative API requests are done on a URI that starts with the `admin` resource end point. Authorization for the administrative API mimics the S3 authorization convention. Some operations require the user to have special administrative capabilities. The response type can be either XML or JSON by specifying the format option in the request, but defaults to the JSON format.

Figure 1.
Basic access diagram

As part of gateway configuration, you can define cross-origin access policies for browser-based applications. These policies can be configured at both the bucket level and the gateway level. For information about configuring a global CORS policy, see Configuring global CORS policy.

### Introduction to WORM

**Write-Once-Read-Many (WORM)** is a secured data storage model that is used to guarantee data protection and data retrieval even in cases where objects and buckets are compromised in production zones.

In IBM Storage Ceph, data security is achieved through the use of S3 Object Lock with read-only capability that is used to store objects and buckets using a Write-Once-Read-Many (WORM) model, preventing them from being deleted or overwritten. They cannot be deleted even by the IBM Storage Ceph administrator.

S3 Object Lock provides two retention modes:

- GOVERNANCE
- COMPLIANCE

These retention modes apply different levels of protection to your objects. You can apply either retention mode to any object version that is protected by Object Lock.

In GOVERNANCE mode, users cannot overwrite or delete an object version or alter its lock settings unless they have special permissions. With GOVERNANCE mode, you can protect objects against deletion by most users, although you can still grant some users permission to alter the retention settings or delete the object if necessary.

In COMPLIANCE mode, a protected object version cannot be overwritten or deleted by any user. When an object is locked in COMPLIANCE mode, its retention mode cannot be changed or shortened.

> 📝 **Note:** Important:

Consulting company Cohasset concludes that IBM Storage Ceph, when properly configured and upon satisfying the additional considerations, meets the electronic record-keeping system requirements of **SEC Rules 17a-4(f)(2)**, **18a-6(e)(2)**, and **FINRA Rule 4511(c)**, as well as, supports the regulated entity in its compliance with the audit system requirements in **SEC Rules 17a-4(f)(3)(iii)** and **18a-6(e)(3)(iii)**. In addition, the assessed capabilities meet the principles-based electronic records requirements of **CFTC Rule 1.31(c)-(d)**. See the [Cohasset certification](https://www.ibm.com/links?url=https%3A%2F%2Fibm.box.com%2Fv%2Fibm-ceph-worm-assessment) for more information.

### Reference

For more details about S3 Object Lock, see the following:

- Enabling object lock for S3

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-object-gateway](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=ceph-object-gateway)*