# README #

## What is this repository for?

* Demo @ SMPTE Bootcamp in MTL 2023
* Config+scripts for automated for a simple ST2110 setup

## Server

Services

* DHCP (and web UI port 3000)
* NMOS registry (mdns+ web UI, port 8000)
* Netbox (port 2000)

[Installation guide](./server/INSTALL.md).

Test services:

```
IP=10.164.50.135
firefox http://$IP:3000  http://$IP:8000/admin/#/ http://$IP:2000/
```

## Scripts:

[Installation guide](./scripts/INSTALL.md).
