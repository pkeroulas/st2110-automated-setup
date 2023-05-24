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
