import argparse
import pickle
import socket

import numpy as np
from PIL import Image

from zad3_1 import merge_image, split_image


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


def server_main(image_path, n_clients, host, port, out_path):
    gray = np.array(Image.open(image_path).convert("L"))
    fragments = split_image(gray, n_clients)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(n_clients)
    print(f"Serwer nasłuchuje na {host}:{port}...")

    processed_fragments = []
    for i in range(n_clients):
        client_socket, client_address = server_socket.accept()
        print(f"Połączono z klientem {i + 1}: {client_address}")

        send_all(client_socket, fragments[i])
        processed_fragment = receive_all(client_socket)
        processed_fragments.append(processed_fragment)
        client_socket.close()

    merge_image(processed_fragments).save(out_path)
    print(f"Obraz przetworzony zapisany jako {out_path}")
    server_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", nargs="?", default="jock.jpg")
    parser.add_argument("-n", type=int, default=2)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=2040)
    parser.add_argument("-o", default="processed_image.png")
    args = parser.parse_args()

    server_main(args.image, args.n, args.host, args.port, args.o)
