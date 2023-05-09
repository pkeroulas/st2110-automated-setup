#!/bin/bash

docker_run () {
    docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
}

playbook='./playbooks/upload.yml'
inventory="./inventories/switch/hosts.yml"
upload="ansible-playbook -vv -i $inventory $playbook"
generate="ansible-playbook -vv -i $inventory --tags netbox,generate,upload $playbook"


echo Cmd exemple: $generate
docker_run
