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

## Upload the switch config

Once entered in the docker container, you'll see a couple of playbook
commands like:

```
ansible-playbook -vv -i ./inventories/switch/hosts.yml ./playbooks/upload.yml
```
