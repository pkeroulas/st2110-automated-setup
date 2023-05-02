# Ansible automation

## Setup

Pre-requisistes: pull docker image that include ansible libs:

```
docker pull deplops/avdbase:3.8.5
```

Pull `ansbile-avd` git submodule and start the docker container:

```
git submodule update --recursive --init
cd ./ansible
docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
```

## Upload the switch config

Once entered in the docker container for AVD:

```
ansible-playbook -vv -i ./inventories/switch/hosts.yml ./playbooks/upload.yml
```
