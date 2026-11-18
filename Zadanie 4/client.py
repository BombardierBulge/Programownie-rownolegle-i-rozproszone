import argparse
import pickle
import socket
import time

import TS  # wymagane, żeby pickle odczytał obiekt problemu (klasa FlowShopProblem)


def send_msg(sock, obj):
    data = pickle.dumps(obj)
    sock.sendall(len(data).to_bytes(4, "big") + data)


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        part = sock.recv(min(65536, n - len(buf)))
        if not part:
            raise ConnectionError("Połączenie zostało zamknięte")
        buf += part
    return bytes(buf)


def recv_msg(sock):
    length = int.from_bytes(recv_exact(sock, 4), "big")
    return pickle.loads(recv_exact(sock, length))


def client_main(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.connect((host, port))

    init = recv_msg(sock)                       # raz: problem + mój chunk ruchów
    if init is None:
        return
    problem, moves = init["problem"], init["moves"]
    print(f"Klient gotowy: {len(moves)} ruchów w chunku")

    while True:
        msg = recv_msg(sock)
        if msg is None:                         # sygnał końca od serwera
            break
        solution = msg["solution"]

        t0 = time.perf_counter()
        costs = []
        for i, j in moves:
            solution[i], solution[j] = solution[j], solution[i]
            costs.append(problem.calculate_makespan(solution))
            solution[i], solution[j] = solution[j], solution[i]   # cofnięcie zamiany
        compute_time = time.perf_counter() - t0

        send_msg(sock, {"costs": costs, "compute_time": compute_time})

    sock.close()
    print("Koniec pracy klienta")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2040)
    args = parser.parse_args()

    client_main(args.host, args.port)