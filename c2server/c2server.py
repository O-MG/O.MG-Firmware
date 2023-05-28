import json
import os
import random as rnd
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
import urllib.request
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import monocypher as mono

provisionFile_ver = 3
SESSION_LIFESPAN = 120
serverPort = 8000
adminPort = 8080

# Provisioning Example:
# python3 ./c2Server.py provision cableOne 60 10 120 cableTwo 30 5 300

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception as e:
        print("Error occurred while getting IP address:", e)
        return None


ip_address = get_ip_address()
if ip_address:
    print("The computer's current IP address is:", ip_address)
else:
    print("Could not determine the computer's IP address.")
hostName = ip_address


def write_c2log(alias, direction, msg):
    with open("c2log", "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{alias}, {timestamp}, {direction}, {msg}\n")

class c2server(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        SimpleHTTPRequestHandler.end_headers(self)

    
    def do_GET(self):
        i = self.path.find("/C2=")
        if i < 0:
            return

        print("------ <GET> ------------------ ", self.path[i:])

        raw_msg = bytearray.fromhex(self.path[i + 4:])
        msg_size = (len(self.path) - 4) / 2
        resp = the_host.process_message(raw_msg, msg_size)

        self.send_response(200)
        if resp is not None:
            self.wfile.write(bytes(resp.hex(), "utf-8"))

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length)
        print(f"------ <POST> ------------------   len: {length}")

        resp = the_host.process_message(body, length)

        if resp is not None:
            self.wfile.write(bytes(resp.hex(), "utf-8"))


class c2admin(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        SimpleHTTPRequestHandler.end_headers(self)

    def handle_C2admin(self):
        with open("c2config", "r") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))
        
    def handle_C2log(self, alias=None, abridge=True):
        if os.path.exists("c2log"):
            with open("c2log", "r") as f:
                lines = f.readlines()
        
            if alias is not None:
                lines = [line for line in lines if line.startswith(alias)]
                
            if abridge:
                lines = [line for line in lines if not re.search(r'.*, out, \n', line)]
        
            content = "".join(lines)
        
            self.send_response(200)
            self.send_header("Content-type", "text/csv")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            log("No c2log file exists.")
            with open("c2log", 'w') as f:
                f.write("")

    def do_GET(self):
                url = urlparse(self.path)
                query_params = parse_qs(url.query)
                alias = query_params.get('alias', [None])[0]
                abridge = query_params.get('abridge', [False])[0]
                        
                if url.path == "/C2admin":
                    self.handle_C2admin()
                elif url.path == "/C2log":
                    self.handle_C2log(alias, abridge)
                elif url.path == "/" or url.path == "/index.html":
                    self.path = "/index.html"
                    super().do_GET()
                else:
                    self.send_response(404)
                    self.end_headers()
    
    def do_POST(self):
        if self.path == "/C2admin":
            content_len = int(self.headers.get("Content-Length"))
            body = self.rfile.read(content_len)
            body_decoded = body.decode("utf-8")
            body_data = json.loads(body.decode("utf-8"))
            alias = body_data.get("alias", "")
            action = body_data.get("action", "")
            data = body_data.get("data", "")
        
            commands = [
                "CI",
                "CV",
                "CWInfo",
                "CNGet",
                "CTList",
                "CFList",
                "CWStatus",
                "CEStatus",
                "CLStatus",
                "CHStatus",
                "C2Status",
                "C2Info"
            ]
        
            client_id = next((device["client_id"] for device in config.devices if device["alias"] == alias), None)
            client = the_host.clients.get(client_id)
            if client and action == "queueAdd":
                if data not in client.cmd_queue:
                    client.cmd_queue.append(data)
                    config.save_provision_files()
                self.send_response(200)
                self.end_headers()
            elif client and action == "queueDelete":
                try:
                    data_int = int(data)
                    log(data_int)
                    client.cmd_queue.pop(data_int)
                    config.save_provision_files()
                    self.send_response(200)
                    self.end_headers()
                except (ValueError, IndexError):
                    self.send_response(400)
                    self.end_headers()
            elif client and action == "queueClear":
                client.cmd_queue = []
                config.save_provision_files()
                self.send_response(200)
                self.end_headers()
            elif client and action == "logClear":
                print(alias);
                if alias == "clearAllLogs":
                    with open("c2log", "w") as f:
                        f.write("")
        
                    for device_client in the_host.clients.values():
                        device_client.cmd_queue = commands + device_client.cmd_queue
                else:
                    with open("c2log", "r") as f:
                        lines = f.readlines()
                    lines = [line for line in lines if not line.startswith(alias)]
                    with open("c2log", "w") as f:
                        f.writelines(lines)
        
                    client.cmd_queue = commands + client.cmd_queue
        
                config.save_provision_files()
                self.send_response(200)
                self.end_headers()
            elif client and action == "logClearAll":
                with open("c2log", "w") as f:
                    f.write("")
                
                for device_client in the_host.clients.values():
                    device_client.cmd_queue = commands + device_client.cmd_queue
                
                config.save_provision_files()
                self.send_response(200)
                self.end_headers()
            elif client and action == "pollInterval":
                alias = body_data.get("alias", "")
                data = body_data.get("data", {})
            
                matching_device = next((device for device in config.devices if device["alias"] == alias), None)
                if matching_device is not None:
                    for key in ["poll_seconds", "fast_seconds", "contact_seconds"]:
                        if key in data:
                            matching_device[key] = data[key]
                            
                config.save_provision_files()
                self.send_response(200)
                self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()
        else:
            super().do_POST()


class Host:
    session_count = 0
    clients = {}
    sessions = {}

    class ClientData:
        def __init__(self, client_id, alias, client_exchange_key, cmd_queue):
            self.client_id = client_id
            self.alias = alias
            self.exchange_key = client_exchange_key
            self.cmd_queue = cmd_queue if cmd_queue else [
                "CI",
                "CV",
                "CWInfo",
                "CNGet",
                "CTList",
                "CFList",
                "CWStatus",
                "CEStatus",
                "CLStatus",
                "CHStatus",
                "C2Status",
                "C2Info"
            ]

    class SessionData:
        def __init__(self, session_id, session_key, client_id, device_id, expires, interface_version):
            self.session_id = session_id
            self.session_key = session_key
            self.client_id = client_id
            self.device_id = device_id
            self.expires = expires
            self.ver = interface_version
            self.msg_count = 0
            self.next_cmd = 0

    def __init__(self, host_private_key, host_public_key):
        self.host_private_key = bytes.fromhex(host_private_key) if host_private_key else None
        self.public_key = bytes.fromhex(host_public_key) if host_public_key else None
        self.session_lifespan = SESSION_LIFESPAN

        config = c2config(self.public_key, self.host_private_key, ip_address, serverPort, adminPort)

        for device in config.devices:
            client_id = device['client_id']
            alias = device['alias']
            client_public_key = bytes.fromhex(device['client_public_key'])
            client_exchange_key = mono.key_exchange(self.host_private_key, client_public_key)
            cmd_queue = device.get('cmd_queue', None)
            client = self.ClientData(client_id, alias, client_exchange_key, cmd_queue)
            self.clients[client_id] = client

    def provision(self, alias, poll_seconds, fast_seconds, contact_seconds):
        global config

        for device in config.devices:
            if device['alias'] == alias:
                print(f"Warning: Existing Device Alias {alias} already exists. Provisioning did not continue.")
                return

        self.session_count += 1
        client_id = rnd.randint(0, 1000000)
        client_secret_key = gen_random(32)
        client_public_key = mono.compute_key_exchange_public_key(client_secret_key)
        client_exchange_key = mono.key_exchange(self.host_private_key, client_public_key)
        client = self.ClientData(client_id, alias, client_exchange_key, None)
        self.clients[client_id] = client

        provision_data = {
            'alias': alias,
            'client_id': client_id,
            'client_public_key': client_public_key.hex(),
            'poll_seconds': poll_seconds,
            'fast_seconds': fast_seconds,
            'contact_seconds': contact_seconds
        }

        config.devices.append(provision_data)
        config.save_provision_files()

        log("Provisioned  [{}]   alias: {}".format(client_id, alias))

        print(f"---------- Provision-file: {alias} ----------")
        device_config = f"host_pk = {self.public_key.hex()},host_url = {hostName},host_port = {serverPort},host_path = \"\",client_id = {client_id},client_sk = {client_secret_key.hex()},poll_rate = {poll_seconds},fast_rate = {fast_seconds},contact_rate = {contact_seconds}"
        print(device_config)
        print('\n\nPlease copy the above Provision-file, log into your O.MG Elite Device’s WebUI, go to Settings -> Net -> C2Config and paste the results, and then press "Change Settings” to apply.')
    def make_err_msg(self, err_code, err_text):
        print("***** Sending Error ", err_code, err_text)
        wrapper = MsgWrapper(109, err_code)
        return wrapper.secure_msg()

    def handle_hello(self, hello_msg, client):
        print("<<<<< Hello Msg >>>>>")
        client_id = client.client_id
        device_id = hello_msg.plain_msg[4:10]
        ver = 1
        if hello_msg.msg_size > 10:
            ver = int.from_bytes(hello_msg.plain_msg[10:11], 'little')
    
        for key in self.sessions:
            session = self.sessions[key]
            if session.client_id == client_id and session.device_id == device_id:
                del (self.sessions[key])
                break
    
        session_key = gen_random(32)
        not_unique = True
        while not_unique:
            session_id = rnd.randint(0, 1000000)
            not_unique = session_id in self.sessions
        expires = int(time.time()) + self.session_lifespan + 5
        self.sessions[session_id] = self.SessionData(session_id, session_key, client_id, device_id, expires, ver)
        print(f"Session id: {session_id}, ver: {ver}, key: {session_key.hex()}")
    
        # Fetch the per-device values from the c2config device entry with the matching client_id
        matching_device = next((device for device in config.devices if device["client_id"] == client.client_id), None)
        if matching_device is not None:
            poll_seconds = matching_device.get("poll_seconds", self.session_lifespan)
            fast_seconds = matching_device.get("fast_seconds", self.session_lifespan)
            contact_seconds = matching_device.get("contact_seconds", poll_seconds)
        else:
            poll_seconds = fast_seconds = contact_seconds = self.session_lifespan
        
        
        plain_resp = HelloResponse(session_id, session_key, self.session_lifespan, poll_seconds, fast_seconds, contact_seconds)
        resp = MsgWrapper(101, plain_resp.text, len(plain_resp.text))
        resp.encrypt(client.exchange_key)
        wrapped_msg = resp.secure_msg()
        print("   secure msg: ", wrapped_msg.hex())
        return wrapped_msg

    def handle_poll(self, poll_msg, session):
        seq_no = int.from_bytes(poll_msg.plain_msg[4:8], 'little')
        script_status = int.from_bytes(poll_msg.plain_msg[8:9], 'little')
        print(f"<<<<< Poll Msg #{seq_no} - SS: {script_status}>>>>>")

        client = self.clients[session.client_id]

        if len(client.cmd_queue) == 0:
            cmd = ""
        else:
            cmd = client.cmd_queue[session.next_cmd % len(client.cmd_queue)]

        cmd_len = len(cmd)
        if cmd_len == 0:
            is_more = 0
        else:
            is_more = 1
        if cmd.startswith("CE") and not cmd.startswith("CEStatus"):
            if session.ver > 1 and script_status != 0:
                cmd = ""
            else:
                session.next_cmd += 1
        else:
            session.next_cmd += 0

        if len(cmd):
            print(f">>>>> Running command {cmd}")
        else:
            print(">>>>> Idle  (No command sent)")

        msg = CommandMsg(seq_no, bytes(cmd, "utf-8"), is_more)
        resp = MsgWrapper(102, msg.text, len(msg.text))
        resp.encrypt(session.session_key)
        wrapped_msg = resp.secure_msg()

        client = self.clients[session.client_id]
        write_c2log(client.alias, "out", cmd)

        return wrapped_msg

    def handle_response(self, command_response, session):
        seq_no = int.from_bytes(command_response.plain_msg[0:4], 'little')
        resp_size = int.from_bytes(command_response.plain_msg[4:6], 'little')
        cmd_offset = 7
        
        try:
            response = command_response.plain_msg[7:].decode('utf-8')
        except UnicodeDecodeError:
            hex_response = command_response.plain_msg[7:].hex()
            split_hex = hex_response.split("09", 1)
            if len(split_hex) > 1:
                try:
                    first_part = bytes.fromhex(split_hex[0]).decode('utf-8')
                    response = first_part + '\t' + split_hex[1]
                except UnicodeDecodeError:
                    response = hex_response
            else:
                response = hex_response
        
        print(f"<<<<< Output for #{seq_no} >>>>>   size: {resp_size} ({len(command_response.plain_msg[7:])})")
        print(response)
        
        client = self.clients[session.client_id]
        write_c2log(client.alias, "in ", response)
        
        cmd = client.cmd_queue.pop(0)  # Remove the cmd from the cmd_queue
        config.save_provision_files()

    def handle_error(self, err_msg, session):
        log("Device error: " + err_msg.plain_text)

    def process_message(self, raw_msg, raw_len):
        if raw_len < 47:
            return self.make_err_msg(101, "Bad message, too short")

        msg = MsgWrapper(raw_msg)

        if msg.msg_type == 1:
            if msg.id not in self.clients:
                return self.make_err_msg(102, "Unknown client-id")
            client = self.clients[msg.id]
            key = client.exchange_key
        else:
            if msg.id not in self.sessions:
                config.load_provision_files()
                return self.make_err_msg(103, "Unknown session-id")
            session = self.sessions[msg.id]
            if session.expires < int(time.time()):
                return self.make_err_msg(104, "Session has expired")
            key = session.session_key

        if not msg.decrypt(key):
            return self.make_err_msg(105, "Invalid encryption")

        if msg.msg_type == 1:
            return self.handle_hello(msg, client)
        if msg.msg_type == 2:
            return self.handle_poll(msg, session)
        elif msg.msg_type == 3:
            return self.handle_response(msg, session)
        elif msg.msg_type == 9:
            return self.handle_error(msg, session)

        return self.make_err_msg(106, "Unknown message-type")


class HelloResponse:
    def __init__(self, session_id, session_key, expiry, poll_seconds, fast_seconds, contact_seconds):
        self.text = bytearray()
        self.text.extend(session_id.to_bytes(4, 'little'))
        self.text.extend(expiry.to_bytes(4, 'little'))
        self.text.extend(session_key)
        self.text.extend(poll_seconds.to_bytes(4, 'little'))
        self.text.extend(fast_seconds.to_bytes(4, 'little'))
        self.text.extend(contact_seconds.to_bytes(4, 'little'))

class CommandMsg:
    def __init__(self, seq, command, is_more):
        cmd_len = len(command)
        self.text = bytearray()
        self.text.extend(seq.to_bytes(4, 'little'))
        self.text.extend(cmd_len.to_bytes(2, 'little'))
        self.text.extend(is_more.to_bytes(1, 'little'))
        self.text.extend(command)
        print("   is_more: ", is_more)


class MsgWrapper:
    def __init__(self, *args):
        if len(args) == 1:
            msg = args[0]
            self.msg_type = msg[0]
            self.id = int.from_bytes(msg[1:5], 'little')
            self.nonce = msg[5:29]
            self.mac = msg[29:45]
            if self.msg_type != 9:
                self.msg_size = int.from_bytes(msg[45:47], 'little')
                self.err_code = 0
            else:
                self.err_code = int.from_bytes(msg[45:47], 'little')
                self.msg_size = 0
            self.encoded = msg[47:47 + self.msg_size]
            self.plain_msg = None
        else:
            self.msg_type = args[0]
            self.id = 0
            self.nonce = None
            self.mac = None
            self.encoded = None
            if len(args) == 2:
                self.err_code = args[1]
                self.msg_size = 0
            else:
                self.plain_msg = args[1]
                self.msg_size = args[2]
                self.err_code = 0

    def encrypt(self, key):
        if self.msg_type == 109:
            return

        self.nonce = gen_random(24)
        self.mac, self.encoded = mono.lock(key, self.nonce, self.plain_msg)

    def decrypt(self, key):
        if self.msg_type == 9:
            return

        self.plain_msg = mono.unlock(key, self.nonce, self.mac, self.encoded)
        if self.plain_msg is None:
            print("   Decrypt failed")
            return False
        return True

    def secure_msg(self):
        msg = bytearray()
        msg.extend(self.msg_type.to_bytes(1, 'little'))
        msg.extend(self.id.to_bytes(4, 'little'))
        if self.msg_type == 9 or self.msg_type == 109:
            msg.extend(bytearray(40))
            msg.extend(self.err_code.to_bytes(2, 'little'))
        else:
            msg.extend(self.nonce)
            msg.extend(self.mac)
            msg.extend(self.msg_size.to_bytes(2, 'little'))
            msg.extend(self.encoded)
        return msg


def log(err_text):
    print("<LOG> ", err_text)


def gen_random(size):
    return bytes(rnd.randint(0, 255) for _ in range(size))


class c2config:
    def __init__(self, host_public_key, host_private_key, host_url, host_port, admin_port):
        self.host_public_key = host_public_key
        self.host_private_key = host_private_key
        self.host_url = host_url
        self.host_port = host_port
        self.admin_port = admin_port
        self.devices = []

        if os.path.exists("c2config"):
            self.load_provision_files()
        else:
            print("No c2config file exists.")
            print('You must provision an O.MG Elite Device before you can use.\n\nEach device provision requires 4 arguments: (alias, poll_seconds, fast_seconds, contact_seconds).\n')
            self.host_private_key = gen_random(32).hex()  # Generate host private key
            self.host_public_key = mono.compute_key_exchange_public_key(
                bytes.fromhex(self.host_private_key)).hex()  # Compute host public key
            self.save_provision_files()  # Save the generated keys

    def save_provision_files(self):
        devices_with_cmd_queue = []
        for device in self.devices:
            client = the_host.clients[device['client_id']]
            device_with_cmd_queue = device.copy()
            device_with_cmd_queue['cmd_queue'] = client.cmd_queue
            devices_with_cmd_queue.append(device_with_cmd_queue)

        config_data = {
            'host_public_key': self.host_public_key,
            'host_private_key': self.host_private_key,
            'host_url': self.host_url,
            'host_port': self.host_port,
            'admin_port': self.admin_port,
            'devices': devices_with_cmd_queue
        }
        with open("c2config", 'w') as f:
            json.dump(config_data, f, indent=4)

    def load_provision_files(self):
        try:
            with open("c2config", 'r') as f:
                if os.path.getsize("c2config") == 0:
                    self.devices = []
                else:
                    config_data = json.load(f)
                    self.host_public_key = config_data['host_public_key']
                    self.host_private_key = config_data['host_private_key']
                    self.host_url = config_data['host_url']
                    self.host_port = config_data['host_port']
                    self.admin_port = config_data['admin_port']
                    self.devices = config_data['devices']
        except FileNotFoundError:
            self.devices = []
            self.host_private_key = gen_random(32).hex()
            self.host_public_key = mono.compute_key_exchange_public_key(
                bytes.fromhex(self.host_private_key)).hex()
            self.save_provision_files()
        except json.JSONDecodeError:
            self.devices = []

def validate_arguments(argv):
            if (len(argv) - 2) % 4 != 0:
                return False, "\nERROR: Incorrect number of arguments.\nEach device provision requires 4 arguments: (alias, poll_seconds, fast_seconds, contact_seconds).\n"
            try:
                for i in range(2, len(argv), 4):
                    int(argv[i + 1])
                    int(argv[i + 2])
                    int(argv[i + 3])
            except ValueError:
                return False, "ERROR: Expected integer values for poll_seconds, fast_seconds, and contact_seconds.\n"
            return True, ""


rnd.seed()
webServer = None

if __name__ == "__main__":
    config = c2config(None, None, ip_address, serverPort, adminPort)
    the_host = Host(config.host_private_key, config.host_public_key)

    for device in config.devices:
        client_id = device['client_id']
        alias = device['alias']
        client_exchange_key = mono.key_exchange(the_host.host_private_key, bytes.fromhex(device['client_public_key']))
        client = the_host.ClientData(client_id, alias, client_exchange_key, device['cmd_queue'])
        the_host.clients[client_id] = client

    config.load_provision_files()

    if len(sys.argv) > 1 and sys.argv[1].lower() == 'provision':
        valid, error_msg = validate_arguments(sys.argv)
        if not valid:
            print(error_msg)
            print("Example usage: python3 ./c2server.py provision cableOne 60 1 300\nExample usage: python3 ./c2server.py provision cableOne 60 1 300 cableTwo 120 1 600")
        else:
            index = 2
            while index < len(sys.argv):
                try:
                    alias = sys.argv[index]
                    poll_seconds = int(sys.argv[index + 1])
                    fast_seconds = int(sys.argv[index + 2])
                    contact_seconds = int(sys.argv[index + 3])
                    the_host.provision(alias, poll_seconds, fast_seconds, contact_seconds)
                    index += 4
                except (IndexError, ValueError):
                    print("Invalid arguments for provisioning. Expected sets of (alias, poll_seconds, fast_seconds, contact_seconds).")
    else:
        try:
            secondaryServer = ThreadingHTTPServer((config.host_url, config.admin_port), c2admin)
            secondaryThread = threading.Thread(target=secondaryServer.serve_forever)
            secondaryThread.daemon = True
            secondaryThread.start()
            print("AdminUI server started http://%s:%s" % (config.host_url, config.admin_port))
        except OSError as e:
            print("Failed to start the AdminUI server.")
            print(e);
            if 'Address already in use' in str(e):
                print(f"Port {config.admin_port} is already in use. Please choose a different port in your c2config.")
            elif 'Can\'t assign requested address' in str(e):
                print(f"Cannot assign requested address: {config.host_url}. Please check the host URL in your c2config.")
            sys.exit(1)

        try:
            webServer = HTTPServer((config.host_url, config.host_port), c2server)
            print("C2 server started http://%s:%s" % (config.host_url, config.host_port))
            with webServer:
                webServer.serve_forever()
        except KeyboardInterrupt:
            print("Server stopped.")
        except OSError as e:
            print(e);
            print("Failed to start the C2 server.")
            if 'Address already in use' in str(e):
                print(f"Port {config.host_port} is already in use. Please choose a different port in your c2config.")
            elif 'Can\'t assign requested address' in str(e):
                print(f"Cannot assign requested address: {config.host_url}. Please check the host URL in your c2config.")
            sys.exit(1)
        finally:
            if webServer is not None:
                webServer.server_close()
                print("Server stopped.")