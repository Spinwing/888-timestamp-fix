import os
import time
import logging
import argparse
import yaml # Requires PyYAML: pip install PyYAML
import re # Added for splitting logic
from datetime import datetime, timedelta
from watchdog.observers.polling import PollingObserver as Observer # Use PollingObserver
from watchdog.events import FileSystemEventHandler

"""
888 Poker Hand History Timestamp Corrector Script
    Monitors an input directory for 888 Poker hand history files, corrects
    the timestamp (adjusting from CT to local time), and writes the modified
    hands to an output directory for use with poker tracking software.

    See README.md for detailed configuration and usage instructions.
    
Disclaimer:
    This script is an unofficial tool created to address a specific timestamp issue
    with 888 Poker hand histories. It is NOT endorsed, supported, or affiliated
    with Poker Copilot or 888 Holdings in any way. Use this script at your own
    risk and responsibility. Ensure it functions correctly with your setup.

Copyright:
    Copyright (c) 2025 Stefano Vedovelli - spnwng@yahoo.it. All rights reserved.
"""

# --- Default Configuration ---
# These values are used if not specified in config file or command line
DEFAULT_CONFIG = {
    'input_dir': None, # Mandatory: Must be set via cmd or config
    'output_dir': None, # Mandatory: Must be set via cmd or config
    'time_difference_hours': 7,
    'log_file': 'hand_history_converter.log', # Default log file in script's dir
    'poll_interval_seconds': 1,
    'file_encoding': 'utf-8',
}
DEFAULT_CONFIG_PATH = 'config.yaml' # Default config file name

# --- Global Variables ---
# These will be populated after parsing config and args
CONFIG = {}
processed_offsets = {} # Dictionary to store the last processed size (offset) for each file

# --- Logging Setup ---
# We configure logging properly after parsing arguments (to get log_file path)
def setup_logging(log_level=logging.INFO, log_file=None):
    """Configures logging based on parsed settings."""
    # Always log to console
    log_handlers = [logging.StreamHandler()]
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(os.path.abspath(log_file))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        log_handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=log_handlers)

# Dictionary to store the last processed size (offset) for each file
# processed_offsets = {} # Defined globally now

def ensure_dir_exists(dir_path):
    """Creates a directory if it doesn't exist."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        logging.info(f"Created directory: {dir_path}")

def adjust_timestamp_in_hand(hand_text):
    """Parses a hand, adjusts the timestamp, and returns the modified hand."""
    # Use splitlines with keepends=True to preserve original newline characters (\n or \r\n)
    lines = hand_text.splitlines(keepends=True)
    output_lines = [] # Store processed lines here
    modified = False
    for line in lines:
        # Find the line with the timestamp marker "***" and date format
        # Check 'modified' flag to avoid processing multiple lines if the pattern accidentally matches elsewhere
        # Example: 0,01 €/0,02 € Blinds No Limit Holdem - *** 30 04 2025 03:00:25
        # Example: 30/60 Blinds No Limit Holdem - *** 28 04 2025 14:15:57
        if not modified and " Blinds No Limit Holdem - *** " in line:
            try:
                parts = line.split(" - *** ")
                if len(parts) == 2:
                    header, timestamp_part = parts # timestamp_part includes the original line ending
                    timestamp_str = timestamp_part.strip() # Strip whitespace (incl. newlines) just for parsing
                    # Parse the timestamp (Format: DD MM YYYY HH:MM:SS)
                    original_dt = datetime.strptime(timestamp_str, "%d %m %Y %H:%M:%S")

                    # Add the time difference
                    corrected_dt = original_dt + timedelta(hours=CONFIG['time_difference_hours'])

                    # Format back to the original string format
                    corrected_timestamp_str = corrected_dt.strftime("%d %m %Y %H:%M:%S")

                    # Find the original line ending (\n or \r\n)
                    ending = ""
                    if timestamp_part.endswith("\r\n"):
                        ending = "\r\n"
                    elif timestamp_part.endswith("\n"):
                        ending = "\n"
                    else:
                        # If the original line didn't end with newline (e.g., last line of file without newline)
                        # or strip removed something unexpected, default to os.linesep
                        ending = os.linesep # Use OS-specific newline

                    # Reconstruct the line with the corrected timestamp and original ending
                    new_line = f"{header} - *** {corrected_timestamp_str}{ending}"
                    output_lines.append(new_line)
                    modified = True
                    logging.debug(f"Adjusted timestamp: {timestamp_str} -> {corrected_timestamp_str}")
                    continue # Skip appending the original line, move to the next line
            except ValueError as e:
                logging.error(f"Could not parse timestamp in line: {line.strip()} - Error: {e}")
                # Fall through to append original line on error
            except Exception as e:
                logging.error(f"An unexpected error occurred processing timestamp line: {line.strip()} - Error: {e}")
                # Fall through to append original line on error

        # If not the timestamp line, or if modification failed, append the original line
        output_lines.append(line)

    if not modified and "#Game No :" in hand_text:
         # Check if the list isn't empty before accessing lines[0]
         first_line_preview = lines[0].strip() if lines else 'N/A'
         logging.warning(f"Could not find or adjust timestamp marker in hand starting with: {first_line_preview}")

    # Join the list of lines back into a single string. Since keepends=True was used,
    # the original line endings are already part of each string in the list.
    return "".join(output_lines)

def process_file(input_filepath):
    """Processes newly added content in a file."""
    filename = os.path.basename(input_filepath)
    output_filepath = os.path.join(CONFIG['output_dir'], filename)

    try:
        # Get the last processed offset, default to 0
        last_offset = processed_offsets.get(input_filepath, 0)
        current_size = os.path.getsize(input_filepath)

        if current_size == last_offset:
            logging.debug(f"No change detected for {filename}")
            return # No new content

        if current_size < last_offset:
             logging.warning(f"File {filename} shrunk? Resetting offset for reading.")
             last_offset = 0 # File might have been reset/overwritten, read from start

        logging.info(f"Processing changes in {filename} from offset {last_offset}")

        # Open output in append mode ('a')
        with open(input_filepath, 'r', encoding=CONFIG['file_encoding'], errors='replace') as infile, \
             open(output_filepath, 'a', encoding=CONFIG['file_encoding']) as outfile:

            infile.seek(last_offset)
            new_content = infile.read()
            # Update offset *after* reading to the current position
            current_offset = infile.tell()
            processed_offsets[input_filepath] = current_offset

            if not new_content:
                logging.info(f"Read empty content from {filename} despite size change?")
                return

            # Split the content by '#Game No :' using a regex lookahead.
            # This splits *before* the delimiter, keeping the delimiter with the subsequent part.
            hands = re.split(r'(?=#Game No :)', new_content)

            processed_any = False
            for hand_text in hands:
                # We check if the chunk actually contains the marker, otherwise it might just be whitespace.
                if hand_text and hand_text.lstrip().startswith("#Game No :"):
                    # Process the hand, preserving internal newlines/spacing
                    processed_hand_text = adjust_timestamp_in_hand(hand_text)
                    outfile.write(processed_hand_text)
                    processed_any = True
                    logging.debug(f"Wrote adjusted hand to {output_filepath}")
                elif hand_text.strip():
                    # The chunk has non-whitespace content but doesn't start with the marker.
                    # This could be data before the first marker in this chunk, or incomplete data.
                    # Log it, but don't write it to avoid corrupting the output file structure.
                    logging.warning(f"Skipping chunk in {filename} that does not start with '#Game No :': '{hand_text[:100].strip()}...'")

            if not processed_any and new_content.strip():
                 logging.warning(f"New content was present in {filename} but no complete hands starting with '#Game No :' were processed in this chunk.")


    except FileNotFoundError:
        logging.warning(f"File not found during processing: {input_filepath}. It might have been deleted quickly.")
        if input_filepath in processed_offsets:
            del processed_offsets[input_filepath] # Clean up state
    except Exception as e:
        logging.exception(f"Error processing file {input_filepath}: {e}")


class HandHistoryHandler(FileSystemEventHandler):
    """Handles file system events for hand history files."""

    def on_modified(self, event):
        """Called when a file or directory is modified."""
        if not event.is_directory:
            # Assuming all files in the input dir are relevant
            logging.info(f"Modification detected: {event.src_path}")
            process_file(event.src_path)

    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory:
            # Assuming all files in the input dir are relevant
            logging.info(f"File created: {event.src_path}. Initializing offset.")
            # Initialize offset for new files
            processed_offsets[event.src_path] = 0
            # Process immediately in case modification event is missed/delayed
            process_file(event.src_path)


def initial_scan(directory):
    """Scans the directory on startup and processes existing files."""
    logging.info(f"Performing initial scan of {directory}...")
    processed_during_scan = set() # Keep track of files processed in this scan

    for filename in os.listdir(directory):
        input_filepath = os.path.join(directory, filename)
        if os.path.isfile(input_filepath):
             # Assuming all files in the input directory should be processed:
            output_filepath = os.path.join(CONFIG['output_dir'], filename)
            processed_during_scan.add(input_filepath) # Mark as seen in input

            try:
                input_size = os.path.getsize(input_filepath)
            except OSError as e:
                logging.error(f"Could not get size of input file {input_filepath}: {e}. Skipping.")
                continue

            if not os.path.exists(output_filepath):
                # Output file does not exist, process the entire input file.
                logging.info(f"Found new input file: {input_filepath}. Processing.")
                processed_offsets[input_filepath] = 0 # Start from beginning
                # Need to ensure output file is created fresh, so open in 'w' then 'a'
                try:
                    with open(output_filepath, 'w', encoding=CONFIG['file_encoding']) as outfile:
                        outfile.write("") # Create/Truncate
                    process_file(input_filepath) # Now process_file appends to the empty file
                except OSError as e:
                    logging.error(f"Could not create/clear output file {output_filepath}: {e}. Skipping processing.")
                    continue # Skip this file if we can't prepare the output
            else:
                # Output file exists, check for alignment.
                try:
                    output_size = os.path.getsize(output_filepath)
                except OSError as e:
                     logging.error(f"Could not get size of output file {output_filepath}: {e}. Assuming output is corrupt, will reprocess input.")
                     processed_offsets[input_filepath] = 0 # Start from beginning
                     try:
                         logging.warning(f"Attempting to clear potentially corrupt output file: {output_filepath}")
                         with open(output_filepath, 'w', encoding=CONFIG['file_encoding']) as outfile:
                             outfile.write("") # Truncate the file
                         logging.info(f"Cleared output file {output_filepath}. Reprocessing input.")
                         process_file(input_filepath) # Reprocess entire file
                     except OSError as e_clear:
                         logging.error(f"Could not clear output file {output_filepath}: {e_clear}. Skipping reprocessing.")
                         # Set offset to avoid processing errors, but file remains out of sync
                         processed_offsets[input_filepath] = input_size
                     continue # Move to next file after handling error

                if input_size > output_size:
                    # Input is larger, process the difference.
                    # process_file appends, so just set the offset correctly.
                    logging.info(f"Input file {input_filepath} is larger than output ({input_size} > {output_size}). Processing appended data.")
                    processed_offsets[input_filepath] = output_size # Start reading from where output left off
                    process_file(input_filepath) # Process only the new part
                elif input_size == output_size:
                    # Sizes match, assume aligned. Set offset to current size.
                    logging.info(f"Input file {input_filepath} and output file are aligned (size {input_size}). Setting offset.")
                    processed_offsets[input_filepath] = input_size
                else: # input_size < output_size
                    # Input is smaller? Unexpected. Log warning and reset processing.
                    logging.warning(f"Input file {input_filepath} ({input_size}) is smaller than output file {output_filepath} ({output_size}). Output may be corrupt. Resetting processing for input file.")
                    # Clear the potentially corrupt output file before reprocessing
                    try:
                        logging.warning(f"Attempting to clear potentially corrupt output file: {output_filepath}")
                        with open(output_filepath, 'w', encoding=CONFIG['file_encoding']) as outfile:
                            outfile.write("") # Truncate the file
                        logging.info(f"Cleared output file {output_filepath}. Reprocessing input.")
                        processed_offsets[input_filepath] = 0
                        process_file(input_filepath)
                    except OSError as e_clear:
                        logging.error(f"Could not clear output file {output_filepath}: {e_clear}. Skipping reprocessing.")
                        processed_offsets[input_filepath] = input_size # Fallback to avoid errors

    # Optional: Check for files in output dir that are *not* in input dir (orphans)
    # for filename in os.listdir(CONFIG['output_dir']):
    #    output_filepath = os.path.join(CONFIG['output_dir'], filename)
    #    input_filepath = os.path.join(directory, filename)
    #    if os.path.isfile(output_filepath) and input_filepath not in processed_during_scan:
    #        logging.warning(f"Orphan output file found (no corresponding input file): {output_filepath}")

    logging.info("Initial scan complete.")

def load_config(config_path):
    """Loads configuration from a YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logging.warning(f"Config file not found at {config_path}. Using defaults/command-line args.")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing config file {config_path}: {e}")
        return {} # Treat as empty on error
    except Exception as e:
        logging.error(f"Unexpected error loading config file {config_path}: {e}")
        return {}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitors 888 Poker hand history files, adjusts timestamps, and writes to a new directory.")
    # Use a positional argument for the config file path
    parser.add_argument('config_path', nargs='?', default=DEFAULT_CONFIG_PATH, help=f"Path to the YAML configuration file (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument('--input-dir', help="Directory where 888 writes original files (overrides config)")
    parser.add_argument('--output-dir', help="Directory where corrected files are written (overrides config)")
    parser.add_argument('--time-diff', type=int, dest='time_difference_hours', help="Time difference in hours (overrides config)")
    parser.add_argument('--log-file', help="Path for the log file (overrides config)")
    parser.add_argument('--encoding', dest='file_encoding', help="File encoding for hand histories (overrides config)")
    parser.add_argument('--poll-interval', type=int, dest='poll_interval_seconds', help="Polling interval in seconds (overrides config)")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging")

    args = parser.parse_args()

    # --- Determine Configuration ---
    # 1. Start with script defaults
    CONFIG = DEFAULT_CONFIG.copy()

    # 2. Load config file if it exists
    yaml_config = load_config(args.config_path) # Use the positional argument name
    if yaml_config:
        CONFIG.update(yaml_config) # Update defaults with values from YAML

    # 3. Override with command-line arguments
    # We only update if the command-line argument was actually provided (is not None)
    cli_args = vars(args)
    for key in CONFIG.keys():
        cli_value = cli_args.get(key)
        if key != 'config_path' and cli_value is not None: # Don't override config_path itself here
            CONFIG[key] = cli_value

    # --- Setup Logging ---
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level, CONFIG['log_file'])

    # --- Validate Mandatory Config ---
    if not CONFIG.get('input_dir') or not CONFIG.get('output_dir'):
        logging.error("Error: input_dir and output_dir must be specified either in the config file or via command-line arguments.")
        parser.print_help()
        exit(1)

    # Ensure directories exist (use absolute paths)
    CONFIG['input_dir'] = os.path.abspath(CONFIG['input_dir'])
    CONFIG['output_dir'] = os.path.abspath(CONFIG['output_dir'])
    ensure_dir_exists(CONFIG['input_dir'])
    ensure_dir_exists(CONFIG['output_dir'])

    logging.info(f"--- Configuration ---")
    for key, value in CONFIG.items():
        logging.info(f"{key}: {value}")
    logging.info(f"Log Level: {logging.getLevelName(log_level)}")
    logging.info(f"---------------------")

    # Perform an initial scan in case files exist / script restarted
    initial_scan(CONFIG['input_dir'])

    event_handler = HandHistoryHandler()
    # Use PollingObserver explicitly
    observer = Observer(timeout=CONFIG['poll_interval_seconds']) # Pass poll interval here
    observer.schedule(event_handler, CONFIG['input_dir'], recursive=False) # Don't watch subdirectories

    observer.start()
    logging.info("Observer started. Press Ctrl+C to stop.")

    try:
        while True:
            # Keep the main thread alive. PollingObserver runs in a separate thread.
            # Sleep for a longer duration as the observer itself is polling
            time.sleep(max(1, CONFIG['poll_interval_seconds'] * 5)) # Sleep longer, e.g., 5x poll interval
    except KeyboardInterrupt:
        logging.info("Stopping observer...")
        observer.stop()
    except Exception as e:
        logging.exception("An unexpected error occurred in the main loop.")
        observer.stop()

    observer.join()
    logging.info("Observer stopped. Exiting.")
