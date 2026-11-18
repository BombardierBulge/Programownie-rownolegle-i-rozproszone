import math
import random
from typing import List, Dict, Tuple, Optional
import os
import multiprocessing as mp
import time

class RandomNumberGenerator:
    def __init__(self, seedValue=None):
        self.__seed = seedValue

    def nextInt(self, low, high):
        m = 2147483647
        a = 16807
        b = 127773
        c = 2836
        k = int(self.__seed / b)
        self.__seed = a * (self.__seed % b) - k * c
        if self.__seed < 0:
            self.__seed = self.__seed + m
        value_0_1 = self.__seed
        value_0_1 = value_0_1 / m
        return low + int(math.floor(value_0_1 * (high - low + 1)))


class FlowShopProblem:
    def __init__(self, jobs: int, machines: int, processing_times: List[List[int]]):
        self.jobs = jobs
        self.machines = machines
        self.processing_times = processing_times

    def calculate_makespan(self, sequence: List[int]) -> int:
        completion_times = [[0] * self.machines for _ in range(self.jobs)]

        for i in range(self.jobs):
            for j in range(self.machines):
                if i == 0 and j == 0:
                    completion_times[i][j] = self.processing_times[sequence[i]][j]
                elif i == 0:
                    completion_times[i][j] = completion_times[i][j - 1] + self.processing_times[sequence[i]][j]
                elif j == 0:
                    completion_times[i][j] = completion_times[i - 1][j] + self.processing_times[sequence[i]][j]
                else:
                    completion_times[i][j] = max(completion_times[i - 1][j], completion_times[i][j - 1]) + \
                                             self.processing_times[sequence[i]][j]

        return completion_times[-1][-1]

    def display_jobs(self):
        print("Generated jobs with processing times:")
        for i in range(self.jobs):
            print(f"Job {i}: {self.processing_times[i]}")

class TabuSearch:
    def __init__(self, problem: FlowShopProblem, tabu_tenure: int, max_iterations: int, rng: RandomNumberGenerator):
        self.problem = problem
        self.tabu_tenure = tabu_tenure
        self.max_iterations = max_iterations
        self.rng = rng

    def initial_solution(self) -> List[int]:
        return list(range(self.problem.jobs))

    def generate_neighbors(self, solution: List[int]) -> List[List[int]]:
        neighbors = []
        for i in range(self.problem.jobs):
            for j in range(i + 1, self.problem.jobs):
                neighbor = solution.copy()
                neighbor[i], neighbor[j] = neighbor[j], neighbor[i]
                neighbors.append(neighbor)
        return neighbors

    def run(self) -> Tuple[List[int], int]:
        current_solution = self.initial_solution()
        best_solution = current_solution.copy()
        best_cost = self.problem.calculate_makespan(current_solution)
        tabu_list = {}

        for iteration in range(self.max_iterations):
            neighbors = self.generate_neighbors(current_solution)
            best_neighbor = None
            best_neighbor_cost = float('inf')

            for neighbor in neighbors:
                neighbor_cost = self.problem.calculate_makespan(neighbor)

                diff_indices = [i for i in range(self.problem.jobs) if current_solution[i] != neighbor[i]]

                if not diff_indices:
                    continue

                move = (min(diff_indices), max(diff_indices))

                if move not in tabu_list or iteration > tabu_list[move] or neighbor_cost < best_cost:
                    if neighbor_cost < best_neighbor_cost:
                        best_neighbor = neighbor
                        best_neighbor_cost = neighbor_cost
                        best_move = move

            if best_neighbor is None:
                continue

            current_solution = best_neighbor
            current_cost = best_neighbor_cost

            if current_cost < best_cost:
                best_solution = current_solution.copy()
                best_cost = current_cost

            tabu_list[best_move] = iteration + self.tabu_tenure

        return best_solution, best_cost

_PROBLEM = None
_MOVE_CHUNKS = None


def _init_worker(problem, move_chunks):
    global _PROBLEM, _MOVE_CHUNKS
    _PROBLEM = problem
    _MOVE_CHUNKS = move_chunks


def _evaluate_chunk(task):
    """Proces roboczy: koszt każdego ruchu (i, j) ze swojego kawałka sąsiedztwa."""
    solution, chunk_id = task
    costs = []
    for i, j in _MOVE_CHUNKS[chunk_id]:
        solution[i], solution[j] = solution[j], solution[i]
        costs.append(_PROBLEM.calculate_makespan(solution))
        solution[i], solution[j] = solution[j], solution[i]   # cofnięcie zamiany
    return costs


class ParallelTabuSearch(TabuSearch):
    def __init__(self, problem: FlowShopProblem, tabu_tenure: int, max_iterations: int,
                 rng: RandomNumberGenerator, n_workers: Optional[int] = None):
        super().__init__(problem, tabu_tenure, max_iterations, rng)
        self.n_workers = n_workers or os.cpu_count() or 1

    def run(self) -> Tuple[List[int], int]:
        n = self.problem.jobs
        moves = [(i, j) for i in range(n) for j in range(i + 1, n)]

        current_solution = self.initial_solution()
        best_solution = current_solution.copy()
        best_cost = self.problem.calculate_makespan(current_solution)
        if not moves:
            return best_solution, best_cost

        size = math.ceil(len(moves) / self.n_workers)
        chunks = [moves[k:k + size] for k in range(0, len(moves), size)]
        tabu_list = {}

        with mp.Pool(len(chunks), initializer=_init_worker,
                     initargs=(self.problem, chunks)) as pool:
            for iteration in range(self.max_iterations):
                tasks = [(current_solution, c) for c in range(len(chunks))]
                parts = pool.map(_evaluate_chunk, tasks)
                costs = [c for part in parts for c in part]

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

        return best_solution, best_cost

def generate_processing_times(jobs: int, machines: int, rng: RandomNumberGenerator, min_time: int = 1,
                              max_time: int = 10) -> List[List[int]]:
    return [[rng.nextInt(min_time, max_time) for _ in range(machines)] for _ in range(jobs)]


if __name__ == "__main__":

    rng = RandomNumberGenerator(seedValue=1432524242)
    jobs, machines = 50, 20
    problem = FlowShopProblem(jobs, machines, generate_processing_times(jobs, machines, rng, 1, 99))

    iters = 5

    for w in (1, 2, 4, os.cpu_count()):
        t = time.perf_counter()
        par = ParallelTabuSearch(problem, 10, iters, rng, n_workers=w).run()
        tp = time.perf_counter() - t
        if w == 1:
            t_seq = tp
            seq = par
        print(f"workers={w}: {tp:.2f}s  speedup={t_seq / tp:.2f}  Cmax={par[1]}  zgodne={par == seq}")