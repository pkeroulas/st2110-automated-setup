# Install

## Pre-requisites

On a debian-based host, install basic tools from the terminal:

```
sudo apt install openssh-server git tig curl docker.io net-tools vim lldpd
sudo usermod -aG docker $USER
```

Also install docker-compose:

```
sudo curl -SL https://github.com/docker/compose/releases/download/v2.17.2/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
```

## Install the package

```
mkdir dev
cd dev
git clone https://pkeroulas@bitbucket.org/cbcrc/st2110-automation-bench.git
cd st2110-automation-bench
git submodule update --init
chmod 755 server/dhcp-glass/bin/dhcpd-pools
echo "$(pwd)/server/status.sh" >> ~/.bashrc
```

## Network config

Need for 2 interfaces:

1) uplink to the site network for users (DHCP)
2) infra gateway for the devices (Static IP)

List the interfaces on the host:

```
ip l
[...]
2: eno1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000
    link/ether 94:c6:91:16:52:8b brd ff:ff:ff:ff:ff:ff
    altname enp0s31f6
3: enx00e04c0208a4: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc fq_codel state DOWN mode DEFAULT group default qlen 1000
    link/ether 00:e0:4c:02:08:a4 brd ff:ff:ff:ff:ff:ff
```

Edit the network config file `./server/netplan.yaml` to set the interface names.
And apply:

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

In `Settings`, set the `Power` to `High performance` and `Never` sleep.

Not sure this is necessary:

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


### Start the service

Configure the http port and copy:

```
cp ./netbox-custom/docker-compose.override.yml ./netbox/docker-compose.override.yml
```

As sudo, configure as an auto-started service:

```
cp ./netbox.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable netbox
systemctl start netbox
# DO NEVER `docker-compose down` this one, the DB would be wiped !!!!
```

`docker ps` command should show netbox containers running.

### Create the users

Create the superuser:

```
cd ./netbox/
docker-compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

Login to the web UI as the superuser and create a normal user (r/w).

Login as the normal user and create an API token (r/w).

### Import initial data

From the UI, import:

- the manufactors: `./netbox-custom/manufacturers.csv`
- the device types: `./netbox-custom/device_types.yaml`