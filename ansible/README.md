# Ansible automation

## Setup

Pre-requisistes: docker

```
docker login https://asd-repo.cbc-rc.ca:43300
docker pull deplops/avdbase
cd ./ansible
docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
```

## Upload the switch config

Once entered in the docker container for AVD:

```
ansible-playbook -vv -i ./inventories/switch/hosts.yml ./playbooks/upload.yml
```
