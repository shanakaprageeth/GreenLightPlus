#!/bin/bash -ex
# author ShanakaPrageeth
# details setup MQTT server, Node-RED, and other dependencies for GreenLight-ADV

DEBIAN_FRONTEND=noninteractive
PROGRAM_NAME="$(basename $0)"
BASEDIR=$(dirname $(realpath "$0"))

export PYTHONPATH=$BASEDIR:$PYTHONPATH

install_dependencies(){
    cd $BASEDIR/
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv npm
    python3 -m venv .venv
    python3 -m pip install --upgrade pip
    python3 -m pip install -r requirnments.txt
    sudo npm install --unsafe-perm node-red
    sudo npm install -g --unsafe-perm node-red
    sudo npm install node-red-dashboard
    sudo npm install -g node-red-dashboard
    source .venv/bin/activate
}

nodered(){
    source .venv/bin/activate
    NODE_RED_JSON="$BASEDIR/node_red_greenlight.json"
    if [ ! -f "$NODE_RED_JSON" ]; then
        echo "Error: $NODE_RED_JSON not found. Please provide the Node-RED flow file."
        exit 1
    fi
    if netstat -tulpn | grep ':1880' > /dev/null
    then
        echo "Node-RED is already running on port 1880."
        cd $BASEDIR/
        curl -X POST http://localhost:1880/flows -H "Content-Type: application/json" --data "@node_red_greenlight.json"
    else
        echo "Node-RED is not running on port 1880. Starting a new instance..."
        node-red -p 1880  --json $BASEDIR/node_red_greenlight.json
        cd $BASEDIR/
        curl -X POST http://localhost:1880/flows -H "Content-Type: application/json" --data "@node_red_greenlight.json"
    fi
}

setup_local_server(){
    install_dependencies
    sudo apt-get install -y mosquitto mosquitto-clients git build-essential terminator screen curl net-tools
    sudo cp /etc/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf.bak
    sudo cp $BASEDIR/mosquitto.conf /etc/mosquitto/conf.d/mosquitto.conf
    sudo systemctl enable mosquitto || true
    sudo service mosquitto restart
    sudo service mosquitto status
    sudo /bin/mkdir -m 740 -p /var/log/mosquitto
    sudo /bin/chown mosquitto:mosquitto /var/log/mosquitto
    sudo /bin/mkdir -m 740 -p /run/mosquitto
    sudo /bin/chown mosquitto:mosquitto /run/mosquitto
    #sudo /usr/sbin/mosquitto -c /etc/mosquitto/mosquitto.conf &
}


if [[ $# -eq 0 ]]; then
    echo "No argument provided. Defaulting to 'all'. Options are: unittests, systemtests, all"
    set -- all
fi

case "$1" in
    install_dependencies)
        install_dependencies
        ;;
    nodered)
        nodered
        ;;
    setup_local_server)
        setup_local_server
        ;;
    *)
        echo "Invalid argument: $1"
        echo "Usage: $PROGRAM_NAME {install_dependencies|setup_local_server|nodered}"
        exit 1
        ;;
esac