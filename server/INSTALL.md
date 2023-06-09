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
sudo chmod a+x /usr/local/bin/docker-compose
```

## Install the package

First, create an ssh key with `ssh-keygen`. Then upload that key in the repo settings to be able to clone on the server.

```
mkdir dev
cd dev
git clone git@bitbucket.org:cbcrc/st2110-automation-bench.git
cd st2110-automation-bench
git submodule update --init
cd ./server/
chmod 755 dhcp-glass/bin/dhcpd-pools
echo "$(pwd)/status.sh" >> ~/.bashrc
```

## Network config

Need for 2 interfaces:

1) uplink to the site network for users (DHCP)
2) infra gateway for the devices (Static IP):
- vlan 2: switch management
- vlan 3: ST 2110 device control

Debian-based OS: edit the network config file `./interfaces` to set the interface names and apply:

```
sudo cp ./interfaces /etc/network/interfaces.d/
sudo systemctl restart networking.service # and pray
```

## Disable Suspend/Hibernate

In `Settings`, set the `Power` to `High performance` and `Never` sleep.

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

Login to the web UI as the superuser and create a normal user (r/w). Then create an API token (r/w) and link to the normal user.

### Import initial data

Login as the normal and import files from [./netbox-custom](./netbox-custom) in the following order:

|*Step*|*Menu Section*|*Import file*|
|------|--------------|-------------|
|1| Netbox Menu > Devices > Manufacturers | [manufacturers.csv](./netbox-custom/manufacturers.csv)
|2| Netbox Menu > Devices > Device Types  | [device_types.yaml](./netbox-custom/device_types.yaml)
|3| Netbox Menu > Devices > Device Roles  | [device_roles.csv ](./netbox-custom/device_roles.csv )
|4| Netbox Menu > Organization > Sites    | [sites.csv        ](./netbox-custom/sites.csv        )
|5| Netbox Menu > IPAM > VLANs            | [VLANs.csv        ](./netbox-custom/VLANS.csv        )
|6| Netbox Menu > Devices > Devices       | [devices.csv      ](./netbox-custom/devices.csv      )
|7| Netbox Menu > Devices > Interfaces    | [interfaces.csv   ](./netbox-custom/interfaces.csv   )

## Riedel Tools

### MNSet:

Test on Debian 11 only. Pre-requisite, install install Java and MongoDB:


```
sudo -i
wget -qO - https://www.mongodb.org/static/pgp/server-5.0.asc | apt-key add -
echo "deb http://repo.mongodb.org/apt/debian bullseye/mongodb-org/5.0 main" | tee /etc/apt/sources.list.d/mongodb-org-5.0.list
apt update
apt-get -y install default-jre gnupg2 wget mongodb-org
```

Get Linux version of MNSet on [Riedel website](https://www.riedel.net/en/downloads/firmware-software) and copy on the server.

```
ls mnset-5.21N-86-x86_64.tgz
mkdir mnset
mnset-5.21N-86-x86_64.tgz
tar xaf mnset-5.21N-86-x86_64.tgz -C mnset
cd ./mnset/
sed -i 's/ubuntu/debian/g' ./common.sh # ONLY if running Debian
sudo install.sh
1) MNSET
Port: 4000
[...]
```

## Verify

```
./status.sh
```
