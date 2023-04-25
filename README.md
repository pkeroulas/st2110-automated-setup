# README #

## What is this repository for?

* Demo @ SMPTE Bootcamp in MTL 2023
* Config+scripts for automated for a simple ST2110 setup

## Server

|*Service*|*HTTP port*|
|---------|-----------|
| Netbox  |      2000 |
| DHCP    |      3000 |
| Riedel MNSet | 4000 |
| NMOS registry| 8000 |

[Installation guide](./server/INSTALL.md).

Test services:

```
IP=10.164.50.135 # server IP for user access
firefox http://$IP:2000  http://$IP:3000/admin/#/ http://$IP:4000/ http:$IP:8000
```

## Infra Network (static)

* server/gateway: 192.168.0.254/24

## Scripts (helpers)

[Installation guide](./scripts/INSTALL.md).

## Ansible

[User guide](./ansible/README.md).
