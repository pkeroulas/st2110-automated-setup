#!/bin/bash

docker_run () {
    docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
}

upload='./playbooks/upload.yml'
flush='./playbooks/flush.yml'
inventory="-i ./inventories/switch/hosts.yml"
ansible="ansible-playbook"

echo "Cmd exemple:
$ansible $inventory $upload
$ansible $inventory $flush
"
docker_run
