
import http.server
import socketserver
import json
import os
import re
import urllib.parse
from datetime import datetime

# Configuration
PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.abspath(os.path.join(BASE_DIR, "../logs"))
PROTOCOL_FILE = os.path.abspath(os.path.join(BASE_DIR, "../protocol_definitions.json"))

# HTML Template
HTML_FILE = os.path.join(BASE_DIR, "index.html")

class LogHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            if os.path.exists(HTML_FILE):
                with open(HTML_FILE, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                 self.wfile.write(b"Error: index.html not found")
            return

        elif path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            try:
                if os.path.exists(LOG_DIR):
                    files = [f for f in os.listdir(LOG_DIR) if f.endswith('.log')]
                    files.sort(reverse=True) # Newest first
                    self.wfile.write(json.dumps(files).encode('utf-8'))
                else:
                    self.wfile.write(b"[]")
            except Exception as e:
                self.wfile.write(json.dumps([]).encode('utf-8'))
            return
            
        elif path.startswith('/api/logs/'):
            filename = path.replace('/api/logs/', '')
            filepath = os.path.join(LOG_DIR, filename)
            
            # Security check
            if os.path.dirname(os.path.abspath(filepath)) != LOG_DIR:
                self.send_error(403, "Access denied")
                return
                
            if not os.path.exists(filepath):
                self.send_error(404, "File not found")
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            parsed_logs = self.parse_log_file(filepath)
            self.wfile.write(json.dumps(parsed_logs).encode('utf-8'))
            return
            
        elif path == '/api/protocol':
             if os.path.exists(PROTOCOL_FILE):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(PROTOCOL_FILE, 'rb') as f:
                    self.wfile.write(f.read())
             else:
                self.send_error(404)
             return

        self.send_error(404)

    def parse_log_file(self, filepath):
        entries = []
        # Regex to match format:
        # [TIMESTAMP] [LEVEL] [DIRECTION] [OPCODE_NAME] | CDB: [HEX] | DATA: [HEX] -> Status=[STATUS]
        # Example: 2026-02-01 00:04:16.976 [INFO] [CMD] SetSpeed             | CDB: 00                   | DATA: [Empty] -> Status=1
        
        # We can split by '|' and then parse parts
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                try:
                    # Basic structure check
                    if '|' in line:
                        parts = line.split('|')
                        left_part = parts[0]
                        
                        # Parse Left: TS [LEVEL] [DIR] NAME
                        # Regex for the brackets part
                        meta_match = re.match(r'^([\d\-\:\. ]+) \[([^\]]+)\] \[([^\]]+)\] (.+)$', left_part.strip())
                        if meta_match:
                            ts, lvl, dir_, name = meta_match.groups()
                        else:
                            # Try parsing EVT which might be different: TS [LEVEL] [EVT] Msg
                            meta_match = re.match(r'^([\d\-\:\. ]+) \[([^\]]+)\] \[EVT\] (.+)$', left_part.strip())
                            if meta_match:
                                ts, lvl, msg = meta_match.groups()
                                entries.append({
                                    'time': ts.strip(),
                                    'level': lvl.strip(),
                                    'dir': 'EVT',
                                    'cmd': 'System Event',
                                    'cdb': '',
                                    'data': msg.strip(),
                                    'status': ''
                                })
                                continue
                            continue
                        
                        # Parse CDB and Data
                        cdb_part = ""
                        data_part = ""
                        status_part = ""
                        
                        if len(parts) > 1:
                            # CDB part usually: " CDB: 00 01 "
                            # Data part usually: " DATA: ... -> Status=1 "
                            
                            rest = "|".join(parts[1:])
                            
                            # Split by "->" for status
                            if '->' in rest:
                                content, status_raw = rest.split('->')
                                status_part = status_raw.replace('Status=', '').strip()
                            else:
                                content = rest
                            
                            # Split content by "| DATA:" if present?
                            # Actually our format is " | CDB: ... | DATA: ... "
                            # So split via pipe is safer
                            
                            # Re-split the original line carefully or trust the pipes
                            # bridge_sem.py: f"{ts} [{level:<4}] [{direction}] {cmd_name:<20} | CDB: {cdb_str:<20} {data_str}-> Status={status}\n"
                            
                            cdb_match = re.search(r'CDB:\s*([0-9a-fA-F ]+)', content)
                            if cdb_match:
                                cdb_part = cdb_match.group(1).strip()
                            
                            data_match = re.search(r'DATA:\s*(.+)$', content)
                            if data_match:
                                data_part = data_match.group(1).strip()
                        
                        entries.append({
                            'time': ts.split(' ')[1], # Just Time for table
                            'level': lvl.strip(),
                            'dir': dir_.strip(),
                            'cmd': name.strip(),
                            'cdb': cdb_part,
                            'data': data_part,
                            'status': status_part
                        })
                except Exception:
                    continue # Skip malformed lines
                    
        return entries

def run():
    print(f"Starting Log Viewer on port {PORT}...")
    print(f"Open http://localhost:{PORT} in your browser")
    print(f"Log Dir: {LOG_DIR}")
    server = http.server.HTTPServer(('0.0.0.0', PORT), LogHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()

if __name__ == '__main__':
    run()
