# README #

## What is this repository for?

* Demo @ SMPTE Bootcamp in MTL 2023
* Config+scripts for automated for a simple ST2110 setup

## Server ##

Services:

* DHCP
* NMOS registry

### Pre-requisites

* debian-based host
* ssh
* git
* curl
* docker
* docker compose

### Install

```
git clone https://pkeroulas@bitbucket.org/cbcrc/st2110-automation-bench.git
cd st2110-automation-bench
```

### Network config

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

### Start the services

```
cd ./server
docker-compose up
```
