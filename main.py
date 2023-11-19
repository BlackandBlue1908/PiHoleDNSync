import os
import yaml
import logging
import json
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_labels(labels):
    processed_labels = {'pihole.dns': [], 'traefik.dns': []}
    for key, value in (labels.items() if isinstance(labels, dict) else 
                       (item.split('=', 1) for item in labels if '=' in item)):
        if key == 'pihole.dns':
            processed_labels['pihole.dns'].extend(value.split(','))
        elif key.startswith('traefik.http.routers.') and key.endswith('.rule'):
            # Extract domain from Traefik rule
            if '`' in value:
                # Format: Host(`example.com`)
                domain = value.split('`')[1]
                processed_labels['traefik.dns'].append(domain)
            else:
                # Log an unrecognized format
                logging.warning(f"Unrecognized Traefik rule format: {value}")
        elif key == 'pihole.hostip':
            processed_labels['pihole.hostip'] = value

    # Log the processed labels for debugging
    logging.info(f"Processed labels: {processed_labels}")
    return processed_labels


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
        # Combine pihole.dns and traefik.dns entries
        dns_names = labels.get('pihole.dns', []) + labels.get('traefik.dns', [])
        host_ip = labels.get('pihole.hostip', 'unknown')
        new_pairs = [f"{host_ip} {dns}" for dns in dns_names]
        old_pairs = previous_data.get(container, {}).get('pairs', ['unknown unknown'])
        if set(new_pairs) != set(old_pairs):
            previous_data[container] = {'pairs': new_pairs, 'old_pairs': old_pairs}
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

        # Read existing lines from the output file
        with open(output_path, 'r') as file:
            existing_lines = set(file.read().splitlines())

        # Update existing_lines based on intermediary data
        for container, data in intermediary_data.items():
            new_pairs = set(data.get('pairs', []))
            old_pairs = set(data.get('old_pairs', []))

            # Remove old pairs
            existing_lines.difference_update(old_pairs)

            # Add new pairs, checking for conflicts
            for new_pair in new_pairs:
                new_dns = new_pair.split(' ')[1]
                conflicting_entry = any(line.split(' ')[1] == new_dns and line not in new_pairs for line in existing_lines)
                if conflicting_entry:
                    logging.warning(f"Conflicting entry found for DNS {new_dns}. Not updating.")
                else:
                    existing_lines.add(new_pair)

        # Write updated lines to the output file
        with open(output_path, 'w') as file:
            for line in sorted(existing_lines):
                file.write(f"{line}\n")

        logging.info(f"Successfully updated {output_path}")

    except FileNotFoundError:
        # Create the file if it doesn't exist and write the new data
        with open(output_path, 'w') as file:
            for line in sorted(existing_lines):
                file.write(f"{line}\n")
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

def process_files(compose_file, intermediary_file, output_file):
    current_labels = read_docker_compose_labels(compose_file)
    previous_labels = read_intermediary_file(intermediary_file)

    update_intermediary_file(intermediary_file, current_labels, previous_labels)
    update_output_file(output_file, intermediary_file)

    logging.info("Processing completed.")

class DockerComposeFileEventHandler(FileSystemEventHandler):
    def __init__(self, compose_file, intermediary_file, output_file):
        self.compose_file = compose_file
        self.intermediary_file = intermediary_file
        self.output_file = output_file

    def on_any_event(self, event):
        # React only to file creation/modification in the directory of the Docker Compose file
        if event.is_directory or not event.event_type in ['created', 'modified']:
            return

        file_dir = os.path.dirname(event.src_path)
        if file_dir == os.path.dirname(self.compose_file):
            logging.info(f"Change detected in the directory of {self.compose_file}, reprocessing...")
            process_files(self.compose_file, self.intermediary_file, self.output_file)

def timed_run(interval, compose_file, intermediary_file, output_file):
    while True:
        try:
            logging.info("Starting timed processing cycle.")
            process_files(compose_file, intermediary_file, output_file)
            logging.info(f"Sleeping for {interval} seconds.")
            time.sleep(interval)
        except Exception as e:
            logging.error(f"Error in timed run: {e}")
            # Optional: Decide if you want to break the loop in case of an error
            # break

def main():
    compose_file = '/compose/docker-compose.yml'
    output_file = '/output/custom.list'
    intermediary_file = '/data/tempdns.json'

    watch_mode = os.getenv('WATCH_MODE', 'False').lower() == 'true'
    timed_mode = os.getenv('TIMED_MODE', 'False').lower() == 'true'
    poll_interval = int(os.getenv('POLL_INTERVAL', 30))


    logging.info(f"Watch Mode: {watch_mode}, Timed Mode: {timed_mode}, Poll Interval: {poll_interval} seconds.")

    if watch_mode:
        event_handler = DockerComposeFileEventHandler(compose_file, intermediary_file, output_file)
        observer = Observer()
        observer.schedule(event_handler, path=os.path.dirname(compose_file), recursive=False)
        observer.start()

    if timed_mode:
        timed_thread = threading.Thread(target=timed_run, args=(poll_interval, compose_file, intermediary_file, output_file))
        timed_thread.daemon = True  # Set this to False if you want the script to wait for this thread to complete
        timed_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if watch_mode:
            observer.stop()
            observer.join()

if __name__ == "__main__":
    main()