import argparse
import os
import socket
import time

import matplotlib.pyplot as plt

from TS import (RandomNumberGenerator, FlowShopProblem, TabuSearch,
                ParallelTabuSearch, generate_processing_times)
from server import DistributedTabuSearch, send_msg

SIZES = [10, 20, 30, 50]
MACHINES = 20
ITERS = 3
REPEATS = 3


def best_time(make_run):
    best, result = float("inf"), None
    for _ in range(REPEATS):
        t = time.perf_counter()
        result = make_run()
        best = min(best, time.perf_counter() - t)
    return best, result


def accept_clients(srv, n):
    srv.settimeout(1.0)
    conns = []
    while len(conns) < n:
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        conn.settimeout(None)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conns.append(conn)
        print(f"Połączono klienta {len(conns)}/{n}: {addr}")
    return conns


def benchmark(conns, client_counts, worker_counts):
    rows = []
    for n in SIZES:
        rng = RandomNumberGenerator(seedValue=1432524242)
        problem = FlowShopProblem(n, MACHINES,
                                  generate_processing_times(n, MACHINES, rng, 1, 99))

        t_seq, ref = best_time(lambda: TabuSearch(problem, 10, ITERS, rng).run())
        row = {"n": n, "seq": t_seq / ITERS, "mp": {}, "dist": {}}

        for w in worker_counts:
            t, res = best_time(
                lambda: ParallelTabuSearch(problem, 10, ITERS, rng, n_workers=w).run())
            assert res == ref, f"multiprocessing: wynik różny od sekwencyjnego (n={n}, w={w})"
            row["mp"][w] = t / ITERS

        for k in client_counts:
            t, res = best_time(
                lambda: DistributedTabuSearch(problem, 10, ITERS, rng, conns[:k]).run())
            assert res == ref, f"klient-serwer: wynik różny od sekwencyjnego (n={n}, k={k})"
            row["dist"][k] = t / ITERS

        rows.append(row)
        print(row, flush=True)
    return rows


def plot(rows, client_counts, worker_counts):
    ns = [r["n"] for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.plot(ns, [r["seq"] for r in rows], "o-", color="black", label="sekwencyjnie")
    for w in worker_counts:
        ax1.plot(ns, [r["mp"][w] for r in rows], "s--", label=f"multiprocessing, {w} proc.")
    for k in client_counts:
        ax1.plot(ns, [r["dist"][k] for r in rows], "o-", label=f"klient-serwer, {k} kl.")
    ax1.set_xlabel("liczba zadań n")
    ax1.set_ylabel("czas jednej iteracji [s]")
    ax1.set_yscale("log")
    ax1.set_title(f"Czas iteracji TS ({MACHINES} maszyn)")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.legend()

    for w in worker_counts:
        ax2.plot(ns, [r["seq"] / r["mp"][w] for r in rows], "s--",
                 label=f"multiprocessing, {w} proc.")
    for k in client_counts:
        ax2.plot(ns, [r["seq"] / r["dist"][k] for r in rows], "o-",
                 label=f"klient-serwer, {k} kl.")
    ax2.axhline(1, color="gray", linestyle="--", linewidth=1)
    ax2.set_xlabel("liczba zadań n")
    ax2.set_ylabel("speedup = T_seq / T")
    ax2.set_title("Przyspieszenie względem wersji sekwencyjnej")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=2,
                        help="ile klientów ma się połączyć (0 = tylko pomiary lokalne)")
    parser.add_argument("--clients", type=int, nargs="+", default=[],
                        help="liczby klientów do porównania (każda <= -n); domyślnie tylko -n")
    parser.add_argument("--workers", type=int, nargs="+",
                        default=sorted({2, os.cpu_count() or 1}),
                        help="liczby procesów multiprocessing do porównania")
    parser.add_argument("--host", default="10.224.206.69")
    parser.add_argument("--port", type=int, default=2040)
    args = parser.parse_args()

    client_counts = args.clients or ([args.n] if args.n > 0 else [])
    assert all(k <= args.n for k in client_counts), "--clients nie może przekraczać -n"

    conns, srv = [], None
    if args.n > 0:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, args.port))
        srv.listen(args.n)
        print(f"Serwer nasłuchuje na {args.host}:{args.port}, czekam na {args.n} klientów...")
        conns = accept_clients(srv, args.n)

    try:
        rows = benchmark(conns, client_counts, args.workers)
    finally:
        for c in conns:
            try:
                send_msg(c, None)
            except OSError:
                pass
            c.close()
        if srv:
            srv.close()

    plot(rows, client_counts, args.workers)