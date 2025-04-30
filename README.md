# 888 Poker Hand History Timestamp Corrector

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Problem Solved

When playing poker on 888 Poker (specifically tested with 888.it), hand history files are generated with timestamps in Central Time (CT). Poker tracking software, like Poker Copilot, often expects these timestamps to be in the user's local time zone (e.g., CET). This discrepancy causes issues with real-time calculations and session reporting in the tracking software.

This script acts as a middleman to fix this issue automatically.

## Features

*   **Monitors** a specified input directory for new or updated 888 Poker hand history files.
*   **Reads** newly appended hands from these files.
*   **Adjusts** the timestamp within each hand history (adds a configurable hour offset, default is +7 for CT to CET).
*   **Writes** the corrected hand histories to corresponding files in a specified output directory.
*   **Preserves** the original file structure, including blank lines between hands.
*   **Handles startup gracefully:** Scans existing files on startup to process missed hands or catch up if the script was stopped.
*   **Configurable:** Uses a YAML file and command-line arguments for setup.

## Requirements

*   Python 3.x
*   `watchdog` library (`pip install watchdog`)
*   `PyYAML` library (`pip install PyYAML`)

## Installation

1.  Clone or download this repository.
2.  Install the required Python libraries:
    ```bash
    pip install watchdog PyYAML
    ```

## Configuration

1.  **Configure 888 Poker Client:** Set your 888 Poker client to save hand histories to a specific directory (this will be your `input_dir`).
2.  **Create Output Directory:** Create an empty directory where the corrected hand histories will be written (this will be your `output_dir`).
3.  **Configure Poker Copilot (or other tracker):** Set your poker tracking software to import hands *only* from the `output_dir`. **Do not** let it import from the `input_dir`.
4.  **Prepare `config.yaml`:**
    *   Copy the sample `config.yaml` provided in this repository.
    *   Edit the file and set **absolute paths** for `input_dir` and `output_dir`.
    *   Adjust `time_difference_hours` if needed (default is 7).
    *   Set the desired `log_file` path and `file_encoding` (usually 'utf-8').

    ```yaml
    # Sample config.yaml
    input_dir: "/full/path/to/your/888_raw_histories" # MANDATORY
    output_dir: "/full/path/to/your/corrected_histories" # MANDATORY
    time_difference_hours: 7
    log_file: "hand_history_converter.log"
    file_encoding: "utf-8"
    poll_interval_seconds: 1
    ```

## Usage

Open your terminal or command prompt, navigate to the script's directory, and run it:

*   **Using default `config.yaml` in the same directory:**
    ```bash
    python 888-timestamp-fix.py
    ```
*   **Specifying a different config file:**
    ```bash
    python 888-timestamp-fix.py /path/to/your/custom_config.yaml
    ```
*   **Overriding config options via command line:**
    ```bash
    python 888-timestamp-fix.py --input-dir /new/input --time-diff 8 --debug
    ```

Leave the script running while you play poker. It will monitor the input directory and process hands as they are written by the 888 client.

## Disclaimer

This script is an unofficial tool created to address a specific timestamp issue with 888 Poker hand histories. It is NOT endorsed, supported, or affiliated with Poker Copilot or 888 Holdings in any way. Use this script at your own risk and responsibility. Ensure it functions correctly with your setup before relying on it.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Copyright

Copyright (c) 2025 Spinwing