# Useful Docker Commands for QuantaLogic Agent

## Building the Image
```bash
# Build the image
docker build -t quantalogic-agent .

# Build with no cache (if you're having issues)
docker build --no-cache -t quantalogic-agent .
```

## Running the Container
```bash
# Run the container (basic)
docker run -p 8082:8082 --name quantalogic-server quantalogic-agent

# Run in detached mode (background)
docker run -d -p 8082:8082 --name quantalogic-server quantalogic-agent

# Run with volume mount for development (replace path with your project path)
docker run -p 8082:8082 -v $(pwd):/app --name quantalogic-server quantalogic-agent
```

## Container Management
```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# Stop the container
docker stop quantalogic-server

# Start a stopped container
docker start quantalogic-server

# Remove the container
docker rm quantalogic-server

# Remove the container forcefully
docker rm -f quantalogic-server
```

## Logs and Debugging
```bash
# View container logs
docker logs quantalogic-server

# Follow container logs
docker logs -f quantalogic-server

# Enter the container shell
docker exec -it quantalogic-server /bin/bash

# View container resource usage
docker stats quantalogic-server
```

## Cleanup
```bash
# Remove unused images
docker image prune

# Remove all stopped containers
docker container prune

# Remove all unused containers, networks, images
docker system prune
```

## Access Points
- Application: http://localhost:8082
- API Documentation: http://localhost:8082/docs
- API Redoc: http://localhost:8082/redoc