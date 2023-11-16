import os
import yaml
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def process_labels(labels):
    relevant_labels = {}
    if isinstance(labels, dict):
        for key, value in labels.items():
            if key in ['pihole.dns', 'pihole.hostip']:
                relevant_labels[key] = value
    elif isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict):
                for key, value in label.items():
                    if key in ['pihole.dns', 'pihole.hostip']:
                        relevant_labels[key] = value
            elif '=' in label:
                key, value = label.split('=', 1)
                if key in ['pihole.dns', 'pihole.hostip']:
                    relevant_labels[key] = value
    return relevant_labels

def read_docker_compose_labels(file_path):
    try:
        with open(file_path, 'r') as file:
            compose_data = yaml.safe_load(file)
            container_labels = {}
            for service_name, service in compose_data['services'].items():
                labels = service.get('labels', {})
                processed_labels = process_labels(labels)
                if processed_labels:
                    container_labels[service_name] = processed_labels
            logging.info(f"Successfully read labels from {file_path}")
            return container_labels
    except Exception as e:
        logging.error(f"Error reading Docker Compose file: {e}")
        return {}

def update_intermediary_file(intermediary_path, data):
    try:
        with open(intermediary_path, 'w') as file:
            json.dump(data, file)
        logging.info(f"Updated intermediary file {intermediary_path}")
    except Exception as e:
        logging.error(f"Error updating intermediary file: {e}")

def read_intermediary_file(intermediary_path):
    try:
        with open(intermediary_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.error(f"Error reading intermediary file: {e}")
        return {}

def update_output_file(output_path, intermediary_data):
    try:
        # Create a mapping from existing hostip-dns pairs to container names
        existing_pairs_to_container = {f"{labels.get('pihole.hostip', 'unknown')} {labels.get('pihole.dns', 'unknown')}": container
                                       for container, labels in intermediary_data.items()}

        # Read existing file and prepare to update lines
        with open(output_path, 'r') as file:
            existing_lines = file.readlines()

        # Create a set for updated content and a set to track which containers have been updated
        updated_content = set()
        updated_containers = set()

        # Update existing lines with new hostip-dns values
        for line in existing_lines:
            line_clean = line.strip()
            if line_clean in existing_pairs_to_container:
                container = existing_pairs_to_container[line_clean]
                new_pair = f"{intermediary_data[container].get('pihole.hostip', 'unknown')} {intermediary_data[container].get('pihole.dns', 'unknown')}"
                updated_content.add(new_pair)
                updated_containers.add(container)
            else:
                updated_content.add(line_clean)

        # Add new hostip-dns pairs for containers not in the updated list
        for container, labels in intermediary_data.items():
            if container not in updated_containers:
                new_pair = f"{labels.get('pihole.hostip', 'unknown')} {labels.get('pihole.dns', 'unknown')}"
                updated_content.add(new_pair)

        # Write updated content
        with open(output_path, 'w') as file:
            for line in sorted(updated_content):
                file.write(f"{line}\n")

        logging.info(f"Successfully updated {output_path}")
    except FileNotFoundError:
        # Create file if it doesn't exist and write new pairs
        with open(output_path, 'w') as file:
            for container, labels in intermediary_data.items():
                pair = f"{labels.get('pihole.hostip', 'unknown')} {labels.get('pihole.dns', 'unknown')}"
                file.write(f"{pair}\n")
        logging.info(f"Created and updated {output_path}")
    except Exception as e:
        logging.error(f"Error updating file: {e}")

# ... rest of the script remains the same




def main():
    compose_file = '/compose/docker-compose.yml'
    output_file = '/output/your-output-file.txt'
    intermediary_file = '/output/intermediary.json'

    current_labels = read_docker_compose_labels(compose_file)
    previous_labels = read_intermediary_file(intermediary_file)

    # Update intermediary file if labels have changed
    if current_labels != previous_labels:
        update_intermediary_file(intermediary_file, current_labels)
        update_output_file(output_file, current_labels)
    else:
        logging.info("No changes in labels detected.")

if __name__ == "__main__":
    main()
