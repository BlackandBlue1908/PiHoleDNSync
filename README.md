# PiHoleDNSync

This container runs a small script that reads your docker compose file and creates Local DNS entries in PiHole via the custom.list file. 

You can do this by setting specific labels per container or if you are using Traefil the script can read your traefik http router labels and use the host names provided there. I created this entire thing using ChatGPT and a ton of trial and error. I am not a developer if you have ways to enhance this please feel free to do so but so far it works for me.



Compose For Container Itself Example:

```
  piholednsync:
    image: ghcr.io/blackandblue1908/piholednsync:main
    container_name: "piholednssync"
    volumes:
      - ./:/compose #Directory of docker-compose.yml
      - ./piholednsync/data:/data #Internal App Data
      - ./etc-pihole:/output #Location of PiHoleDNS /etc-pihole directory
    environment:
      - WATCH_MODE=true #Watches compose file for changes (Does not work on Docker for Windows)
      - TIMED_MODE=false #Checks for changes at the Poll Interval
      - POLL_INTERVAL=9000
      - PROCESS_TRAEFIK=true #Determine if Traefik router labels are used as DNS names for a given container
      - DEFAULT_HOST_IP=192.168.1.1 #Used if no Hot IP set in a given container.
```

Example of target container
```
 whoami2:
    image: "traefik/whoami"
    container_name: "simple-service"
    labels:
      - pihole.hostip=10.0.0.111
      - pihole.dns= "pihole1.example.com, pihole2.example.com, pihole3.example.com"
      - traefik.http.routers.readarr.rule=Host(`test.test.com`) || Host(`test.test.lan`) || Host(`test.local`)
      - "traefik.http.routers.tools.rule=Host(`sample.sample.lan`,`sample.lan`)"

```
In this example a total of 8 Local DNS Entries will be added to the custom.list of pihole:
- pihole1.example.com 10.0.0.111
- pihole2.example.com 10.0.0.111
- pihole3.example.com 10.0.0.111
- test.test.com 10.0.0.111
- test.test.lan 10.0.0.111
- test.local 10.0.0.111
- sample.sample.lan 10.0.0.111
- sample.lan 10.0.0.111
