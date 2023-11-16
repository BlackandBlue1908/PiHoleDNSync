import os
import yaml
import logging
import json
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_labels(labels):
    return {key: value for key, value in (labels.items() if isinstance(labels, dict) else 
            (item.split('=', 1) for item in labels if '=' in item)) if key in ['pihole.dns', 'pihole.hostip']}

def read_docker_compose_labels(file_path):
    try:
        with open(file_path, 'r') as file:
            compose_data = yaml.safe_load(file)
            return {service_name: process_labels(service.get('labels', {}))
                    for service_name, service in compose_data['services'].items()}
    except Exception as e:
        logging.error(f"Error reading Docker Compose file: {e}")
        return {}

def read_intermediary_file(intermediary_path):
    try:
        with open(intermediary_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.error(f"Error reading intermediary file: {e}")
        return {}

def update_intermediary_file(intermediary_path, current_data, previous_data):
    updated = False
    for container, labels in current_data.items():
        new_pair = f"{labels.get('pihole.hostip', 'unknown')} {labels.get('pihole.dns', 'unknown')}"
        old_pair = previous_data.get(container, {}).get('pair', 'unknown unknown')
        if new_pair != old_pair:
            previous_data[container] = {'pair': new_pair, 'old_pair': old_pair}
            updated = True

    if updated:
        try:
            with open(intermediary_path, 'w') as file:
                json.dump(previous_data, file)
            logging.info(f"Updated intermediary file {intermediary_path}")
        except Exception as e:
            logging.error(f"Error updating intermediary file: {e}")

def update_output_file(output_path, intermediary_path):
    try:
        with open(intermediary_path, 'r') as file:
            intermediary_data = json.load(file)
        with open(output_path, 'r') as file:
            existing_lines = set(file.read().splitlines())

        new_pairs = {data.get('pair') for data in intermediary_data.values() if data.get('pair')}
        
        for container, data in intermediary_data.items():
            old_pair = data.get('old_pair')
            if old_pair and old_pair in existing_lines and old_pair != data.get('pair'):
                existing_lines.remove(old_pair)
                logging.info(f"Removed old pair for container {container}: {old_pair}")

        updated_lines = existing_lines.union(new_pairs)

        with open(output_path, 'w') as file:
            for line in sorted(updated_lines):
                file.write(f"{line}\n")

        logging.info(f"Successfully updated {output_path}")
    except FileNotFoundError:
        with open(output_path, 'w') as file:
            for pair in new_pairs:
                file.write(f"{pair}\n")
        logging.info(f"Created and populated new {output_path}")
    except Exception as e:
        logging.error(f"Error updating file: {e}")

def watch_for_changes(filename, interval=5):
    last_modified = None
    while True:
        try:
            # Check last modified time
            current_modified = os.path.getmtime(filename)
            if last_modified is None or current_modified > last_modified:
                last_modified = current_modified
                yield True
            else:
                yield False
        except FileNotFoundError:
            logging.error(f"File {filename} not found.")
            yield False
        time.sleep(interval)

def main():
    compose_file = '/compose/docker-compose.yml'
    output_file = '/output/your-output-file.txt'
    intermediary_file = '/output/intermediary.json'

    for file_changed in watch_for_changes(compose_file):
        if file_changed:
            logging.info(f"{compose_file} has changed, processing...")
            current_labels = read_docker_compose_labels(compose_file)
            previous_labels = read_intermediary_file(intermediary_file)

            update_intermediary_file(intermediary_file, current_labels, previous_labels)
            update_output_file(output_file, intermediary_file)

            logging.info("Processing completed.")

if __name__ == "__main__":
    main()