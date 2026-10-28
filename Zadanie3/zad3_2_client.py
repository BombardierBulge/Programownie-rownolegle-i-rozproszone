import argparse
import pickle
import socket

from zad3_1 import sobel_fragment


def send_all(sock, data):
    data = pickle.dumps(data)
    sock.sendall(len(data).to_bytes(4, byteorder="big"))
    sock.sendall(data)


def receive_all(sock):
    length = int.from_bytes(sock.recv(4), byteorder="big")
    data = b""
    while len(data) < length:
        packet = sock.recv(4096)
        if not packet:
            break
        data += packet
    return pickle.loads(data)


def client_main(host, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))

    fragment = receive_all(client_socket)
    processed_fragment = sobel_fragment(fragment)
    send_all(client_socket, processed_fragment)

    client_socket.close()
    print("Fragment przetworzony i wysłany z powrotem do serwera")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2040)
    args = parser.parse_args()

    client_main(args.host, args.port)
