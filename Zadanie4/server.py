import argparse
import math
import pickle
import socket
import time

from TS import (FlowShopProblem, RandomNumberGenerator, TabuSearch,
                generate_processing_times)


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


class DistributedTabuSearch(TabuSearch):
    def __init__(self, problem, tabu_tenure, max_iterations, rng, conns):
        super().__init__(problem, tabu_tenure, max_iterations, rng)
        self.conns = conns
        self.compute_time = 0.0

    def run(self):
        n = self.problem.jobs
        moves = [(i, j) for i in range(n) for j in range(i + 1, n)]

        current_solution = self.initial_solution()
        best_solution = current_solution.copy()
        best_cost = self.problem.calculate_makespan(current_solution)
        if not moves:
            return best_solution, best_cost

        size = math.ceil(len(moves) / len(self.conns))
        chunks = [moves[k * size:(k + 1) * size] for k in range(len(self.conns))]
        tabu_list = {}

        try:
            for conn, chunk in zip(self.conns, chunks):
                send_msg(conn, {"problem": self.problem, "moves": chunk})

            for iteration in range(self.max_iterations):
                for conn in self.conns:
                    send_msg(conn, {"solution": current_solution})
                replies = [recv_msg(conn) for conn in self.conns]

                costs = [c for r in replies for c in r["costs"]]
                self.compute_time += max(r["compute_time"] for r in replies)

                best_move = None
                best_neighbor_cost = float('inf')
                for move, cost in zip(moves, costs):
                    if move not in tabu_list or iteration > tabu_list[move] or cost < best_cost:
                        if cost < best_neighbor_cost:
                            best_neighbor_cost = cost
                            best_move = move

                if best_move is None:
                    continue

                i, j = best_move
                current_solution[i], current_solution[j] = current_solution[j], current_solution[i]

                if best_neighbor_cost < best_cost:
                    best_solution = current_solution.copy()
                    best_cost = best_neighbor_cost

                tabu_list[best_move] = iteration + self.tabu_tenure
        finally:
            for conn in self.conns:
                try:
                    send_msg(conn, None)
                except OSError:
                    pass

        return best_solution, best_cost


def server_main(args):
    rng = RandomNumberGenerator(seedValue=args.seed)
    problem = FlowShopProblem(args.jobs, args.machines,
                              generate_processing_times(args.jobs, args.machines, rng, 1, 99))

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(args.n)
    print(f"Serwer nasłuchuje na {args.host}:{args.port}, czekam na {args.n} klientów...")

    conns = []
    for k in range(args.n):
        conn, addr = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conns.append(conn)
        print(f"Połączono klienta {k + 1}/{args.n}: {addr}")

    if args.baseline:
        t = time.perf_counter()
        seq = TabuSearch(problem, args.tenure, args.iters, rng).run()
        t_seq = time.perf_counter() - t
        print(f"Sekwencyjnie: {t_seq:.2f}s  Cmax={seq[1]}")

    ts = DistributedTabuSearch(problem, args.tenure, args.iters, rng, conns)
    t = time.perf_counter()
    res = ts.run()
    t_dist = time.perf_counter() - t

    print(f"Rozproszone ({args.n} klientów): {t_dist:.2f}s  Cmax={res[1]}")
    print(f"  liczenie u klientów (najwolniejszy, suma): {ts.compute_time:.2f}s")
    print(f"  narzut (sieć + serializacja + wybór ruchu): {t_dist - ts.compute_time:.2f}s")
    if args.baseline:
        print(f"  speedup={t_seq / t_dist:.2f}  zgodne={res == seq}")

    for c in conns:
        send_msg(c, None)
        c.close()
    srv.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=2, help="liczba klientów")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=2040)
    parser.add_argument("--jobs", type=int, default=50)
    parser.add_argument("--machines", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1432524242)
    parser.add_argument("--iters", type=int, default=5)
    parser.add_argument("--tenure", type=int, default=10)
    parser.add_argument("--baseline", action="store_true",
                        help="najpierw uruchom wersję sekwencyjną i porównaj")
    args = parser.parse_args()

    server_main(args)