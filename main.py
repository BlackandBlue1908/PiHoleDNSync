import docker
import yaml

def read_docker_compose_labels(file_path):
    # Read and parse Docker Compose file
    with open(file_path, 'r') as file:
        compose_data = yaml.safe_load(file)
        # Extract labels (assuming they are in services)
        labels = [service.get('labels', {}) for service in compose_data['services'].values()]
    return labels

def append_to_file(file_path, data):
    # Append data to a file
    with open(file_path, 'a') as file:
        file.write(str(data))

def main():
    labels = read_docker_compose_labels('docker-compose.yml')
    append_to_file('output.txt', labels)

if __name__ == "__main__":
    main()
