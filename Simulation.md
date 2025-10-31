1. Install dependencies

```
./setup_server.sh install_dependencies
```

2. Run local MQTT server

```
./setup_server.sh setup_local_server
```

3. Setup Nodered instance

```
./setup_server.sh nodered
```

3. Execute the simulation

```
source .venv/bin/activate
./build.sh
python3 simulation.py
```

## TODO 

### simulation png image graph should rearranged and track older variables