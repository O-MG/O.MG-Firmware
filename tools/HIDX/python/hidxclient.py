import os
import sys
import socket
import logging
import argparse
import threading
	
def pad_input(input_str):
	padding_length = (8 - (len(input_str) % 8)) % 8
	padded_str = input_str + ' ' * padding_length
	return padded_str

def recvlog(msg):
	print(f"{msg}",)
	logger_received.info(msg)

def handle_client(client_socket,run):
	while run.is_set():
		data = None
		try:
			# suspect this needs to be smaller to ensure data comes out evenly
			data = client_socket.recv(1024).decode()
		except OSError as e:
			run.clear()
			print(f"Socket Exception: {e}")
			break
		# double check the data
		if not data:
			recvlog("!!!! Socket has disconnected....")
			client_socket.close()
			run.clear()
			break
		else:
			pprint(data)
			recvlog(f">{data}")
	
def console_input(client_socket,run):
	print("HIDX Shell (type '%quit' to exit)")
	while run.is_set():
		user_input = input("$ ")
		if user_input == "%exit":
			client_socket.close()
			run = False
			break
		try:
			padded_input = pad_input(user_input + "\n")
			if logger_sent:
				logger_sent.info(padded_input)
			client_socket.sendall(padded_input.encode())
		except OSError as e:
			print(f"Socket Exception: {e}")
			run.clear()
			break

def start_server(host, port):
	server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

	run = threading.Event()
	run.set()

	try:
		server_socket.bind((host, port))
		server_socket.listen(1)
		print(f"]\nServer listening on {host}:{port}")
	
		while run:
			client_socket, addr = server_socket.accept()
			recvlog(f"!!!! Client connected from {addr[0]}:{addr[1]}")

			client_thread = threading.Thread(target=handle_client, args=(client_socket,run,))
			client_thread.start()

			console_thread = threading.Thread(target=console_input, args=(client_socket,run,))
			console_thread.start()
	except OSError as e:
		print(f"Error with socket: {e}")
		run.clear()
	finally:
		server_socket.close()

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="HIDXClient")
	parser.add_argument("host", type=str, nargs="?", default="0.0.0.0", help="address to bind to")
	parser.add_argument("port", type=int, nargs="?", default=1234, help="port to listen on")
	parser.add_argument("sendlog", type=str, nargs="?", help="message send log")
	parser.add_argument("recvlog", type=str, nargs="?", default="hidxrecv.log", help="message receive log (for loot)")
	args = parser.parse_args()
	
	global logger_received, logger_sent
	logger_received = logging.getLogger("received_data")
	logger_received.addHandler(logging.FileHandler(args.recvlog))
	logger_received.setLevel(logging.INFO)
	logger_sent = None
	if args.sendlog:
		logger_sent = logging.getLogger("sent_data")
		logger_sent.addHandler(logging.FileHandler(args.sendlog))
		logger_sent.setLevel(logging.INFO)

	start_server(args.host, args.port)
