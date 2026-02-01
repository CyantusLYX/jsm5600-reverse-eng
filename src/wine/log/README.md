# SEM32 Log Viewer

A lightweight, web-based log viewer for SEM32 bridge logs.

## Features
- **Real-time Parsing**: Reads logs from `../logs/`.
- **Search & Filter**: Filter by Log Level (INFO, WARN, ERR) and text search.
- **Protocol Integration**: Loads commands from `../protocol_definitions.json`.
- **Zero Dependencies**: Runs with standard Python 3.

## Usage
1.  Run the viewer:
    ```bash
    python3 log_viewer.py
    ```
2.  Open your browser to:
    [http://localhost:8080](http://localhost:8080)

## Requirements
- Python 3.x
- Modern Web Browser (Internet connection required for Tailwind/Vue CDN, or cache them locally).
