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
    processed = {}
    for key, value in (labels.items() if isinstance(labels, dict) else 
            (item.split('=', 1) for item in labels if '=' in item)):
        if key == 'pihole.dns':
            try:
                dns_values = parse_dns_values(value)
                processed[key] = dns_values
            except Exception as e:
                logging.error(f"Error processing DNS values: {e}")
                processed[key] = ()
        elif key == 'pihole.hostip':
            processed[key] = value
    return processed


def parse_dns_values(dns_string):
    # Trim leading and trailing characters ('(' and ')')
    dns_string = dns_string.strip("()")

    # Split the string by comma and strip extra whitespace and quotes
    dns_values = [value.strip(" '\"") for value in dns_string.split(',')]

    return tuple(dns_values)


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
        host_ip = labels.get('pihole.hostip', 'unknown')
        dns_values = labels.get('pihole.dns', ())

        for dns in dns_values:
            new_pair = f"{host_ip} {dns}"
            # Use a combination of container name and DNS as the key
            unique_key = f"{container}_{dns}"
            old_pair = previous_data.get(unique_key, 'unknown unknown')
            if new_pair != old_pair:
                previous_data[unique_key] = {'pair': new_pair, 'old_pair': old_pair}
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

        for container, data in intermediary_data.items():
            new_pair = data.get('pair')
            old_pair = data.get('old_pair')

            # Extract DNS name from the pair for comparison
            new_dns = new_pair.split(' ')[1] if new_pair else ''
            old_dns = old_pair.split(' ')[1] if old_pair else ''

            # Check if the DNS name already exists with a different IP
            conflicting_entry = any(line.split(' ')[1] == new_dns and line != old_pair for line in existing_lines)
            if conflicting_entry:
                logging.warning(f"Conflicting entry found for DNS {new_dns}. Not updating.")
                continue

            # Update existing_lines with the new pair
            if old_pair:
                existing_lines.discard(old_pair)
            if new_pair:
                existing_lines.add(new_pair)

        with open(output_path, 'w') as file:
            for line in sorted(existing_lines):
                file.write(f"{line}\n")

        logging.info(f"Successfully updated {output_path}")

    except FileNotFoundError:
        with open(output_path, 'w') as file:
            for line in existing_lines:
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
