import os
import yaml
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_labels(labels):
    relevant_labels = []
    if isinstance(labels, dict):
        for key, value in labels.items():
            if key.startswith('piholedns'):
                relevant_labels.append({key: value})
    elif isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict):
                for key, value in label.items():
                    if key.startswith('piholedns'):
                        relevant_labels.append({key: value})
            elif '=' in label:
                key, value = label.split('=', 1)
                if key.startswith('piholedns'):
                    relevant_labels.append({key: value})
    return relevant_labels

def read_docker_compose_labels(file_path):
    try:
        with open(file_path, 'r') as file:
            compose_data = yaml.safe_load(file)
            all_labels = []
            for service in compose_data['services'].values():
                labels = service.get('labels', {})
                processed_labels = process_labels(labels)
                all_labels.extend(processed_labels)
            logging.info(f"Successfully read labels from {file_path}")
            return all_labels
    except Exception as e:
        logging.error(f"Error reading Docker Compose file: {e}")
        return []

def append_to_file(file_path, data, host_ip):
    try:
        with open(file_path, 'a') as file:
            for label in data:
                for key, value in label.items():
                    file.write(f"{host_ip} {key}: {value}\n")
        logging.info(f"Successfully appended labels to {file_path}")
    except Exception as e:
        logging.error(f"Error writing to file: {e}")

def main():
    compose_file = '/compose/docker-compose.yml'
    output_file = '/output/your-output-file.txt'
    host_ip = os.getenv('HOST_IP', 'localhost')

    labels = read_docker_compose_labels(compose_file)
    if labels:
        append_to_file(output_file, labels, host_ip)
    else:
        logging.info("No labels found or error occurred while reading labels.")

if __name__ == "__main__":
    main()
