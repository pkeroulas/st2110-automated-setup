# Install #

## Pre-requisites

* debian-based host
* ssh
* git
* curl
* docker
* docker compose

## Install the package

```
git clone https://pkeroulas@bitbucket.org/cbcrc/st2110-automation-bench.git
cd st2110-automation-bench
git submodule update --init
chmod 755 server/dhcp-glass/bin/dhcpd-pools
```

## Network config

* uplink to the site network for users (DHCP)
* interface connected to the bench for the devices (Static IP)

Install the network config

```
sudo cp ./server/netplan.yaml /etc/netplan/01-network-manager-all.yaml
sudo netplan apply
ip a
2: eno1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 94:c6:91:16:52:8b brd ff:ff:ff:ff:ff:ff
    altname enp0s31f6
    inet 10.164.50.135/23 brd 10.164.51.255 scope global dynamic noprefixroute eno1             <------------------- site IP (users)
       valid_lft 537sec preferred_lft 537sec
    inet6 fe80::96c6:91ff:fe16:528b/64 scope link 
       valid_lft forever preferred_lft forever
3: enx00e04c0208a4: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 00:e0:4c:02:08:a4 brd ff:ff:ff:ff:ff:ff
    inet 192.168.0.254/24 brd 192.168.0.255 scope global noprefixroute enx00e04c0208a4          <------------------ server IP for the bench
       valid_lft forever preferred_lft forever
    inet6 fe80::2e0:4cff:fe02:8a4/64 scope link 
       valid_lft forever preferred_lft forever
```

## Disable Suspend/Hibernate

```
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
sudo vi /etc/systemd/sleep.conf
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
```

## Setup the infra services (dhcp, nmos, glass)

As sudo:

```
cp ./infra.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable infra
systemctl start infra
```

## Netbox

Configure the http port and start:

```
cp ./netbox-custom/netbox.docker-compose.override.yml ./netbox/
cd ./netbox/
docker-compose up
# DONT docker-compose down on this one, the DB is wipded
```

Create the superuser on 1st exec:

```
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

Login to the web UI: (port 2000) and import initial data:

- the manufactors: `./netbox-custom/manufacturers.csv`
- the device types: `./netbox-custom/device_types.yaml`
