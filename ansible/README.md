# Ansible automation

## Setup

Pre-requisistes: pull docker image that include ansible libs and
pynetbox libs:

```
docker pull deplops/avdbase:3.8.5
```

Pull `ansbile-avd` git submodule and start the docker container:

```
git submodule update --recursive --init
cd ./ansible
./run.sh
```

Enter a dummy password for the vault as this demo project doesn't use any vault.

## Upload the switch config

Once entered in the docker container, you'll see a couple of playbook
commands like:

```
ansible-playbook -i ./inventories/switch/hosts.yml   ./playbooks/upload_sw_config.yml
ansible-playbook -i ./inventories/gateways/hosts.yml ./playbooks/upload_gw_config.yml
```

## Recover the switch config:

Plug this: Switch-console-port <-> RJ-45-to-DB9 <-> DB9-to-USB <-> config-server
Then from the terminal of the config-server:

```
stty -F /dev/ttyUSB0 9600 cs8 -cstopb -parenb #8bit, no paraity, 1 stop bit
sudo microcom -s 9600 -p /dev/ttyUSB0
admin:admin
copy startup-config running-config
```
