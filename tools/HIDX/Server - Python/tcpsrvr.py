#   tcpsrvr  Quick & dirty tcp client tester

import ctypes as ct

import socket
import sys

tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_address = ("192.168.5.155", 5252)
tcp_socket.bind(server_address)
tcp_socket.listen(1)

flood_msg = b'a012345678b012345678c012345678d012345678e012345678f012345678g012345678h012345678i012345678j012345678'

def btoi(num_str):
    val = 0
    for c in num_str:
        if val == 0 and c == 32:
            continue
        if c < 48 or c > 57:
            break
        val = val * 10 + (c - 48)

    return val


while True:
    print("Waiting for connection")
    connection, client = tcp_socket.accept()

    try:
        print("Connected to client IP: {}".format(client))

        # Receive and print data 32 bytes at a time, as long as the client is sending something
        i = 0
        total_bytes = 0
        while True:
            data = connection.recv(256)
            if len(data) == 0:
                break
            # print("Received data: {}".format(data))
            print(".", end="")
            total_bytes += len(data)
            i += 1
            if i >= 50:
                i = 0
                print("   Total: {}".format(total_bytes))
            # ncssrrrr
            mtype = data[0]
            ftype = data[1]
            if mtype >= 48 and mtype <= 57 and ftype == 70:
                size = btoi(data[2:4])
                if size == 0:
                    size = 100
                repeat = btoi(data[4:])
                if repeat == 0:
                    repeat = 200
                total_flood = 0
                big_msg = b''
                for i in range(size):
                    big_msg += flood_msg
                msglen = len(big_msg)
                print()
                print("Flooding {} ({})...".format(repeat, msglen), end="")
                for i in range(repeat):
                    connection.send(big_msg)
                    total_flood += msglen
                print("   Sent bytes: ", total_flood)
            else:
                connection.send(data)

            if not data:
                break

    finally:
        connection.close()