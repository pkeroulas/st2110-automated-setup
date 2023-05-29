#!/bin/bash

docker_run () {
    docker run --rm -it -v ${PWD}:/projects deplops/avdbase:3.8.5
}

echo q | ./help.sh

docker_run
