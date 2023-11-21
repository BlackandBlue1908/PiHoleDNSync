# PiHoleDNSync

Playing with a python script that polls docker-compose.yml for changes and updates custom.list DNS names based on labels in compose


Compose Example:
  piholednsync:
    image: ghcr.io/blackandblue1908/piholednsync:main
    container_name: "piholednssync"
    volumes:
      - ./:/compose
      - ./piholednsync/data:/data
      - ./etc-pihole:/output
    environment:
      - WATCH_MODE=true #Watches compose file for changes (Does not work on Docker for Windows)
      - TIMED_MODE=false #Checks for changes at the Poll Interval
      - POLL_INTERVAL=9000 
      - DEFAULT_HOST_IP=192.168.1.1 #Used if no Hot IP set in service.
