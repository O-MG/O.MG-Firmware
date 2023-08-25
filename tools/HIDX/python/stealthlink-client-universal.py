import os
import sys
import socket
import select
import logging
import binascii
import argparse
import threading

from datetime import datetime
from time import sleep
from pprint import pprint

# X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*
# amsibufferscan


# current issues:
""" 
1. input prompt prompt may return before content is finished so you will see things like
$whoami
$root
if you want to fix this easily, just hit another enter as soon as you send a message
2. the universal client + universal python target code are slower then native or powershell
3. ascii characters are primarily *only* supported, other characters may be stripped
4. recvlog doesn't buffer data for efficiency purposes, error checking should (and will) be added later
this will also fix #1
5. this client is currently mac or linux only due to select()
"""


## These we can set but aren't meant to be changed regularly
## So not a part of the user inputs and flags
nowait = True # wait or not wait for end of message control characters 
remote_prompt = False # hide the > prompt and presume it comes from the client
windows = False # enable larger buffer, please don't trun this on unless testing!!!!
delay = None # delay between messages (0.2-0.5 is fine) default to None

def non_blocking_input(prompt="", timeout=5):
    print(prompt, end='', flush=True)
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        return sys.stdin.readline().strip()
    else:
        return None

def pad_input(input_str, left_pad=False, right_pad=False, chunk_size = 8):
    if left_pad and right_pad:
        raise Exception("Cannot add padding on both the left and right side!")
    # default to right pad
    if not left_pad and not right_pad:
        right_pad = True
    padding_length = (chunk_size - (len(input_str) % chunk_size)) % chunk_size
    padded_str = None
    if isinstance(input_str, bytes):
        input_str = input_str.decode("utf-8")
    if right_pad:
        padded_str = input_str + ' ' * padding_length    
    if left_pad:
        padded_str = ' ' * padding_length + input_str
    return padded_str

def split_output(message,chunk_size=8):
    chunks = []
    for i in range(0,len(message),chunk_size):
        raw_message = message[i:i+chunk_size]
        padded_message = pad_input(raw_message,right_pad=True)
        chunks.append(padded_message)
    return chunks
    
def recvlog(msg):
    print(f"{msg}",end="")
    logger_received.info(msg)

def handle_client(client_socket,run,rts):
    global nowait
    no_data_count = 0
    while run.is_set():
        data = None
        try:
            # suspect this needs to be smaller
            rlist, _, _ = select.select([client_socket], [], [], 1.0)  # Wait
            if client_socket in rlist:
                data = client_socket.recv(1024).decode()
            else:
                # timeout
                no_data_count+=1
                #print("I AM HERE")
                data = " "
        except OSError as e:
            run.clear()
            print(f"Socket Exception: {e}")
            break
        
        """
        print("\nSTART INCOMING DATA")
        print(f"{data}")
        print(binascii.hexlify(bytes(data,'utf-8')))
        print("END INCOMING DATA")
        """
        
        # double check the data
        if not data:
            recvlog("!!!! Socket has disconnected....")
            client_socket.close()
            run.clear()
            break
        else:
            if "\x07\x17" in data or nowait:
                rts.set()
            elif "SH" in data:
                data = data.strip("\n")
                rts.set()
            elif data == "" and no_data_count>=2:
                rts.set()
            #print("Status: %s"%str(rts.is_set()))
            recvlog(f"{data}")
    
def console_input(client_socket,run,rts):
    print("\nHIDX Shell (type '%quit' to exit)")
    global nowait, windows, delay, remote_prompt
    debug_send = False
    split_messages = True
    while run.is_set():
        if rts.is_set():
            prompt_msg = "\r$"
            user_input = ""
            if debug_send:
                dt = datetime.now().strftime("%M:%S.%f")
                user_input = f"CLI {dt}"
            else:
                if remote_prompt:
                    prompt_msg = ""
                print(prompt_msg, end='', flush=True)
                user_input = non_blocking_input(timeout=2)
                if not user_input:
                	continue
                if user_input == "%exit":
                    client_socket.close()
                    run.clear()
                    break
            try:
                raw_input = user_input + "\n\x07\x17\00"
                if windows:
                    raw_input =pad_input(raw_input,right_pad=True,chunk_size=64)
                if logger_sent:
                    logger_sent.info(raw_input)
                output = None
                if split_messages:
                    output = split_output(raw_input)
                    for m in output:
                        client_socket.sendall(m.encode())
                        if delay:
                            sleep(float(delay))
                else:
                    output = padded_input.encode()
                    client_socket.sendall(output)
                if not nowait:
                    rts.clear()
            except OSError as e:
                print(f"Socket Exception: {e}")
                run.clear()
                client_socket.close()
                break

def hidxcli(host, port,reuse=True):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if reuse:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    run = threading.Event()
    run.set()
    
    rts = threading.Event()
    rts.set()

    try:
        server_socket.bind((host, port))
        server_socket.listen(1)
        print(f"Server listening on {host}:{port}")
    
        while run:
            client_socket, addr = server_socket.accept()
            print()
            recvlog(f"!!!! Client connected from {addr[0]}:{addr[1]}")
            rts.set()
            client_thread = threading.Thread(target=handle_client, args=(client_socket,run,rts,))
            client_thread.start()

            console_thread = threading.Thread(target=console_input, args=(client_socket,run,rts,))
            console_thread.start()
    except OSError as e:
        print(f"Error with socket: {e}")
        run.clear()
    finally:
        print("Attempting to close..")
        server_socket.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client")
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

    hidxcli(args.host, args.port)


