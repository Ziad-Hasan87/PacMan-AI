from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from collections import deque
import argparse
import math
import random

maze_layout = [
    "############################",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#.####.#####.##.#####.####.#",
    "#..........................#",
    "#.####.##.########.##.####.#",
    "#......##.########.##.####.#",
    "######.##....##....##.######",
    ".....#.#####.##.#####.#.....",
    ".....#.#####.##.#####.#.....",
    ".....#.##..........##.#.....",
    "######.##.###__###.##.######",
    "..........#......#..........",
    "######.##.#......#.##.######",
    ".....#.##.#......#.##.#.....",
    ".....#.##.########.##.#.....",
    ".....#.##..........##.#.....",
    "######.##.########.##.######",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#...##................##...#",
    "###.##.##.########....##.###",
    "###.##.##.########.##.##.###",
    "#......##....##....##......#",
    "#.##########.##.##########.#",
    "#.##########.##.##########.#",
    "#..........................#",
    "############################",
]
base_maze_layout = list(maze_layout)
maze = [list(row) for row in base_maze_layout]
DOT_TILES = {'o'}
TOTAL_DOTS = sum(row.count('o') for row in base_maze_layout)


def update_maze_from_state(state):
    """Rebuild the visible maze from maze_layout and overlay actors/state."""
    global maze, maze_layout
    maze = [list(row) for row in base_maze_layout]

    # Remove consumed collectible dots from the current visible maze.
    for r in range(len(maze)):
        for c in range(len(maze[r])):
            if base_maze_layout[r][c] in DOT_TILES and (r, c) not in state.dots:
                maze[r][c] = ' '

    hr, hc = state.hero
    maze[hr][hc] = 'H'

    for gr, gc in state.ghosts:
        maze[gr][gc] = 'G'

    # Keep maze_layout synchronized with the latest visible maze.
    maze_layout = ["".join(row) for row in maze]


def output(state):
    """Display the current state of the maze."""
    update_maze_from_state(state)
    print("\n".join("".join(row) for row in maze))


def _finalize_state(state):
    """Ensure every returned state also refreshes the visible maze."""
    update_maze_from_state(state)
    return state

@dataclass(frozen=True)
class GameState:
    hero: Tuple[int, int]
    ghosts: Tuple[Tuple[int, int], ...]
    dots: frozenset[Tuple[int, int]]
    turn: str
    dice: int
    game_end: bool = False
    winner: Optional[str] = None


@dataclass
class _MCTSNode:
    state: GameState
    hero_turn_index: int
    ghost_turn_index: int
    depth: int
    parent: Optional["_MCTSNode"] = None
    move: Optional[Tuple[int, int]] = None
    visits: int = 0
    value_sum: float = 0.0
    children: List["_MCTSNode"] = field(default_factory=list)
    untried_moves: List[Tuple[int, int]] = field(default_factory=list)

def move_hero(state, new_position, new_dice):
    r1, c1 = state.hero
    r2, c2 = new_position
    
    new_dots = state.dots

    if r1 == r2:
        if c2 > c1:
            step = 1
        else:
            step = -1
        for c in range(c1 + step, c2 + step, step):
            if (r1, c) in state.ghosts:
                return _finalize_state(GameState(
                    hero = (r1, c),
                    ghosts = state.ghosts,
                    dots = new_dots,
                    turn = "GHOST",
                    dice = new_dice,
                    game_end = True,
                    winner = "GHOST"
                ))
            if (r1, c) in new_dots:
                new_dots = new_dots - {(r1, c)}

    else:
        if r2 > r1:
            step = 1
        else:
            step = -1
        for r in range(r1 + step, r2 + step, step):
            if (r, c1) in state.ghosts:
                return _finalize_state(GameState(
                    hero = (r, c1),
                    ghosts = state.ghosts,
                    dots = new_dots,
                    turn = "GHOST",
                    dice = new_dice,
                    game_end = True,
                    winner = "GHOST"
                ))
            if (r, c1) in new_dots:
                new_dots = new_dots - {(r, c1)}

    if len(new_dots) == 0:
        return _finalize_state(GameState(
            hero = new_position,
            ghosts = state.ghosts,
            dots = new_dots,
            turn = "GHOST",
            dice = new_dice,
            game_end = True,
            winner = "HERO"
        ))
    return _finalize_state(GameState(
        hero=new_position,
        ghosts=state.ghosts,
        dots=frozenset(new_dots),
        turn="GHOST",
        dice=new_dice,
        game_end = False,
        winner = None
    ))
def move_ghost(state, new_position, new_dice):
    ghosts = list(state.ghosts)
    ghosts[0] = new_position
    ghosts_tuple = tuple(ghosts)

    # Check if ghost catches the hero
    if new_position == state.hero:
        return _finalize_state(GameState(
            hero=state.hero,
            ghosts=ghosts_tuple,
            dots=state.dots,
            turn="HERO",
            dice=new_dice,
            game_end=True,
            winner="GHOST"
        ))

    return _finalize_state(GameState(
        hero=state.hero,
        ghosts=ghosts_tuple,
        dots=state.dots,
        turn="HERO",
        dice=new_dice,
        game_end=False,
        winner=None
    ))

hero_moves = []
ghost1_moves = []
ghost2_moves = []


def _get_agent_queue(agent):
    if agent == "HERO":
        return hero_moves
    if agent == "GHOST1":
        return ghost1_moves
    if agent == "GHOST2":
        return ghost2_moves
    raise ValueError(f"Unknown agent: {agent}")


def _distance_for_turn(agent, turn_offset=0):
    """Return max move distance for an agent at a future turn offset."""
    queue = _get_agent_queue(agent)
    while len(queue) <= turn_offset:
        queue.append(random.randint(1, 6))
    return max(1, queue[turn_offset])

def generate_next_move(agent):
    move = random.randint(1, 6)
    queue = _get_agent_queue(agent)
    queue.append(move)
    return move
    
def get_next_move(agent):
    queue = _get_agent_queue(agent)
    if not queue:
        generate_next_move(agent)
    return queue.pop(0)
    
def initialize_game():
    hero_moves.clear()
    ghost1_moves.clear()
    ghost2_moves.clear()

    hero_start = (23, 13)
    ghost_starts = [(11, 13)]
    dots = set()
    for r in range(len(base_maze_layout)):
        for c in range(len(base_maze_layout[r])):
            if base_maze_layout[r][c] in DOT_TILES:
                dots.add((r, c))
                
    for i in range(0,100):
        generate_next_move("HERO")
        generate_next_move("GHOST1")
        generate_next_move("GHOST2")
        
    return _finalize_state(GameState(
        hero=hero_start,
        ghosts=tuple(ghost_starts),
        dots=frozenset(dots),
        turn="HERO",
        dice=0
    ))

def heroistics(state):
    if state.game_end:
        if state.winner == "HERO":
            return 10**9
        if state.winner == "GHOST":
            return -(10**9)

    hero_r, hero_c = state.hero
    distance_to_dots = _shortest_path_distance((hero_r, hero_c), state.dots) if state.dots else 0

    # Primary objective: consume 'o'. Secondary: move toward nearest remaining 'o'.
    dots_eaten = TOTAL_DOTS - len(state.dots)
    return dots_eaten * 10000 - distance_to_dots


def ghost_heuristic(state):
    """Higher is better for GHOST: minimize shortest-path distance to HERO."""
    if state.game_end:
        if state.winner == "GHOST":
            return 10**9
        if state.winner == "HERO":
            return -(10**9)

    ghost_pos = state.ghosts[0]
    hero_pos = state.hero
    distance_to_hero = _shortest_path_distance(ghost_pos, {hero_pos})
    return -distance_to_hero


def _shortest_path_distance(start, targets):
    """BFS shortest-path distance from start to the nearest target over walkable tiles."""
    if not targets:
        return 0
    if start in targets:
        return 0

    rows = len(base_maze_layout)
    cols = len(base_maze_layout[0])
    queue = deque([(start[0], start[1], 0)])
    visited = {start}

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    while queue:
        r, c, dist = queue.popleft()
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            next_pos = (nr, nc)

            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if base_maze_layout[nr][nc] == '#':
                continue
            if next_pos in visited:
                continue

            if next_pos in targets:
                return dist + 1

            visited.add(next_pos)
            queue.append((nr, nc, dist + 1))

    # Unreachable target fallback (should not happen on this map).
    return rows * cols


def _is_walkable(position):
    r, c = position
    return (
        0 <= r < len(base_maze_layout)
        and 0 <= c < len(base_maze_layout[r])
        and base_maze_layout[r][c] != '#'
    )


def _get_linear_moves(start_position, steps):
    """Return all straight-line moves up to steps in 4 directions."""
    max_steps = max(1, steps)
    candidates = []
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for dr, dc in directions:
        r, c = start_position
        for _ in range(max_steps):
            r += dr
            c += dc
            if not _is_walkable((r, c)):
                break
            candidates.append((r, c))

    return candidates


def _minimax(state, depth, is_hero_turn, hero_turn_index=0, ghost_turn_index=0):
    if depth == 0 or state.game_end:
        return heroistics(state), None

    if is_hero_turn:
        move_steps = _distance_for_turn("HERO", hero_turn_index)
        hero_candidates = _get_linear_moves(state.hero, move_steps)
        if not hero_candidates:
            return heroistics(state), state.hero

        best_value = float('-inf')
        best_move = hero_candidates[0]

        for candidate in hero_candidates:
            next_ghost_distance = _distance_for_turn("GHOST1", ghost_turn_index)
            next_state = move_hero(state, candidate, next_ghost_distance)
            value, _ = _minimax(
                next_state,
                depth - 1,
                False,
                hero_turn_index + 1,
                ghost_turn_index,
            )
            if value > best_value:
                best_value = value
                best_move = candidate

        return best_value, best_move

    move_steps = _distance_for_turn("GHOST1", ghost_turn_index)
    predicted_ghost_move = _predict_ghost_chase_move(state, move_steps)
    next_hero_distance = _distance_for_turn("HERO", hero_turn_index)
    next_state = move_ghost(state, predicted_ghost_move, next_hero_distance)
    value, _ = _minimax(
        next_state,
        depth - 1,
        True,
        hero_turn_index,
        ghost_turn_index + 1,
    )

    return value, None


def minimax_hero_move(state, max_depth):
    """Pick the HERO move that maximizes heroistics over a depth-limited minimax tree."""
    if max_depth < 1:
        return state.hero, heroistics(state)

    if state.turn != "HERO":
        raise ValueError("minimax_hero_move requires state.turn == 'HERO'")

    best_value, best_move = _minimax(state, max_depth, True)

    # Minimax explores simulated states that update the global display; restore current one.
    update_maze_from_state(state)

    return best_move, best_value


def _predict_ghost_chase_move(state, move_steps):
    """Minimax ghost model: chase HERO by minimizing shortest-path distance."""
    candidates = _get_linear_moves(state.ghosts[0], move_steps)
    if not candidates:
        return state.ghosts[0]

    return min(
        candidates,
        key=lambda pos: _shortest_path_distance(pos, {state.hero}),
    )


def _legal_moves_for_state(state, hero_turn_index, ghost_turn_index):
    if state.turn == "HERO":
        steps = _distance_for_turn("HERO", hero_turn_index)
        return _get_linear_moves(state.hero, steps)

    steps = _distance_for_turn("GHOST1", ghost_turn_index)
    return _get_linear_moves(state.ghosts[0], steps)


def _apply_turn_move(state, move, hero_turn_index, ghost_turn_index):
    if state.turn == "HERO":
        next_ghost_distance = _distance_for_turn("GHOST1", ghost_turn_index)
        next_state = move_hero(state, move, next_ghost_distance)
        return next_state, hero_turn_index + 1, ghost_turn_index

    next_hero_distance = _distance_for_turn("HERO", hero_turn_index)
    next_state = move_ghost(state, move, next_hero_distance)
    return next_state, hero_turn_index, ghost_turn_index + 1


def _uct_select_child(node, exploration_constant):
    parent_visits = max(1, node.visits)
    best_score = float('-inf')
    best_child = node.children[0]

    for child in node.children:
        if child.visits == 0:
            return child

        average_value = child.value_sum / child.visits
        exploration = exploration_constant * math.sqrt(
            math.log(parent_visits) / child.visits
        )

        # Ghost maximizes ghost_heuristic, Hero minimizes it.
        if node.state.turn == "GHOST":
            score = average_value + exploration
        else:
            score = -average_value + exploration

        if score > best_score:
            best_score = score
            best_child = child

    return best_child


def _rollout_policy_move(state, hero_turn_index, ghost_turn_index):
    legal_moves = _legal_moves_for_state(state, hero_turn_index, ghost_turn_index)
    if not legal_moves:
        return None

    if state.turn == "GHOST":
        # Rollout ghost policy: chase HERO by shortest path.
        return min(legal_moves, key=lambda pos: _shortest_path_distance(pos, {state.hero}))

    # Rollout hero policy: greedy one-step heroistics.
    best_move = legal_moves[0]
    best_value = float('-inf')
    for move in legal_moves:
        next_state, _, _ = _apply_turn_move(state, move, hero_turn_index, ghost_turn_index)
        value = heroistics(next_state)
        if value > best_value:
            best_value = value
            best_move = move

    return best_move


def _rollout_ghost_value(state, hero_turn_index, ghost_turn_index, depth, max_depth):
    current_state = state
    current_depth = depth
    current_hero_index = hero_turn_index
    current_ghost_index = ghost_turn_index

    while not current_state.game_end and current_depth < max_depth:
        move = _rollout_policy_move(current_state, current_hero_index, current_ghost_index)
        if move is None:
            break

        current_state, current_hero_index, current_ghost_index = _apply_turn_move(
            current_state,
            move,
            current_hero_index,
            current_ghost_index,
        )
        current_depth += 1

    return ghost_heuristic(current_state)


def _mcts_ghost_move(state, max_depth=8, iterations=200, exploration_constant=1.4):
    """UCT MCTS for ghost action selection at the current state."""
    if state.turn != "GHOST":
        raise ValueError("_mcts_ghost_move requires state.turn == 'GHOST'")

    root = _MCTSNode(
        state=state,
        hero_turn_index=0,
        ghost_turn_index=0,
        depth=0,
    )
    root.untried_moves = _legal_moves_for_state(state, 0, 0)

    if not root.untried_moves:
        return state.ghosts[0]

    for _ in range(iterations):
        node = root

        # Selection: traverse fully expanded tree.
        while (
            node.children
            and not node.untried_moves
            and not node.state.game_end
            and node.depth < max_depth
        ):
            node = _uct_select_child(node, exploration_constant)

        # Expansion: add one new child if possible.
        if (
            not node.state.game_end
            and node.depth < max_depth
            and node.untried_moves
        ):
            move = random.choice(node.untried_moves)
            node.untried_moves.remove(move)

            next_state, next_hero_index, next_ghost_index = _apply_turn_move(
                node.state,
                move,
                node.hero_turn_index,
                node.ghost_turn_index,
            )

            child = _MCTSNode(
                state=next_state,
                hero_turn_index=next_hero_index,
                ghost_turn_index=next_ghost_index,
                depth=node.depth + 1,
                parent=node,
                move=move,
            )
            child.untried_moves = _legal_moves_for_state(
                child.state,
                child.hero_turn_index,
                child.ghost_turn_index,
            )
            node.children.append(child)
            node = child

        # Simulation
        reward = _rollout_ghost_value(
            node.state,
            node.hero_turn_index,
            node.ghost_turn_index,
            node.depth,
            max_depth,
        )

        # Backpropagation
        while node is not None:
            node.visits += 1
            node.value_sum += reward
            node = node.parent

    # Pick root child with best average ghost value.
    best_child = max(
        root.children,
        key=lambda child: (child.value_sum / child.visits) if child.visits else float('-inf'),
    ) if root.children else None

    # MCTS explores simulated states that update the global display; restore current one.
    update_maze_from_state(state)

    if best_child is None or best_child.move is None:
        return root.untried_moves[0]
    return best_child.move


def _step_game_state(state, minimax_depth, ghost_mcts_depth, ghost_mcts_iterations):
    """Advance the game by exactly one turn and return transition metadata."""
    if state.game_end:
        return state, {"actor": None, "move": None, "distance": None}

    if state.turn == "HERO":
        best_move, _ = minimax_hero_move(state, minimax_depth)
        hero_distance = get_next_move("HERO")
        next_ghost_distance = _distance_for_turn("GHOST1", 0)
        next_state = move_hero(state, best_move, next_ghost_distance)
        return next_state, {
            "actor": "HERO",
            "move": list(best_move),
            "distance": hero_distance,
        }

    ghost_distance = _distance_for_turn("GHOST1", 0)
    ghost_move = _mcts_ghost_move(
        state,
        max_depth=ghost_mcts_depth,
        iterations=ghost_mcts_iterations,
    )
    _ = get_next_move("GHOST1")
    next_hero_distance = _distance_for_turn("HERO", 0)
    next_state = move_ghost(state, ghost_move, next_hero_distance)
    return next_state, {
        "actor": "GHOST",
        "move": list(ghost_move),
        "distance": ghost_distance,
    }


def _serialize_state(state, turn_count, stopped_by_user=False, last_transition=None):
    update_maze_from_state(state)
    return {
        "maze_layout": maze_layout,
        "hero": list(state.hero),
        "ghosts": [list(g) for g in state.ghosts],
        "turn": state.turn,
        "game_end": state.game_end,
        "winner": state.winner,
        "dots_remaining": len(state.dots),
        "hero_heuristic": heroistics(state),
        "ghost_heuristic": ghost_heuristic(state),
        "turn_count": turn_count,
        "stopped_by_user": stopped_by_user,
        "last_transition": last_transition,
    }


backend_session = {
    "state": None,
    "turn_count": 0,
    "stopped_by_user": False,
    "minimax_depth": 4,
    "ghost_mcts_depth": 8,
    "ghost_mcts_iterations": 200,
    "last_transition": None,
}


def _reset_backend_session(minimax_depth=4, ghost_mcts_depth=8, ghost_mcts_iterations=200):
    backend_session["state"] = initialize_game()
    backend_session["turn_count"] = 0
    backend_session["stopped_by_user"] = False
    backend_session["minimax_depth"] = minimax_depth
    backend_session["ghost_mcts_depth"] = ghost_mcts_depth
    backend_session["ghost_mcts_iterations"] = ghost_mcts_iterations
    backend_session["last_transition"] = None


def _ensure_backend_session():
    if backend_session["state"] is None:
        _reset_backend_session(
            backend_session["minimax_depth"],
            backend_session["ghost_mcts_depth"],
            backend_session["ghost_mcts_iterations"],
        )


def create_app():
    from flask import Flask, jsonify, request
    from flask_cors import CORS

    app = Flask(__name__)
    CORS(app)

    @app.get("/api/state")
    def get_state():
        _ensure_backend_session()
        payload = _serialize_state(
            backend_session["state"],
            backend_session["turn_count"],
            backend_session["stopped_by_user"],
            backend_session["last_transition"],
        )
        return jsonify(payload)

    @app.post("/api/start")
    def start_game():
        body = request.get_json(silent=True) or {}
        minimax_depth = int(body.get("minimax_depth", backend_session["minimax_depth"]))
        ghost_mcts_depth = int(body.get("ghost_mcts_depth", backend_session["ghost_mcts_depth"]))
        ghost_mcts_iterations = int(body.get("ghost_mcts_iterations", backend_session["ghost_mcts_iterations"]))

        _reset_backend_session(minimax_depth, ghost_mcts_depth, ghost_mcts_iterations)

        payload = _serialize_state(
            backend_session["state"],
            backend_session["turn_count"],
            backend_session["stopped_by_user"],
            backend_session["last_transition"],
        )
        return jsonify(payload)

    @app.post("/api/signal")
    def signal_game():
        _ensure_backend_session()
        body = request.get_json(silent=True) or {}
        action = (body.get("action") or "continue").strip().lower()

        if action in {"quit", "exit", "stop"}:
            backend_session["stopped_by_user"] = True
            payload = _serialize_state(
                backend_session["state"],
                backend_session["turn_count"],
                backend_session["stopped_by_user"],
                backend_session["last_transition"],
            )
            return jsonify(payload)

        if action != "continue":
            return jsonify({"error": "Unsupported action. Use 'continue' or 'quit'."}), 400

        state = backend_session["state"]
        if state.game_end or backend_session["stopped_by_user"]:
            payload = _serialize_state(
                state,
                backend_session["turn_count"],
                backend_session["stopped_by_user"],
                backend_session["last_transition"],
            )
            return jsonify(payload)

        next_state, transition = _step_game_state(
            state,
            backend_session["minimax_depth"],
            backend_session["ghost_mcts_depth"],
            backend_session["ghost_mcts_iterations"],
        )
        backend_session["state"] = next_state
        backend_session["turn_count"] += 1
        backend_session["last_transition"] = transition

        payload = _serialize_state(
            backend_session["state"],
            backend_session["turn_count"],
            backend_session["stopped_by_user"],
            backend_session["last_transition"],
        )
        return jsonify(payload)

    return app


def run_game_loop(
    max_turns=200,
    minimax_depth=3,
    ghost_mcts_depth=8,
    ghost_mcts_iterations=200,
    show_board=True,
    wait_for_input=True,
):
    """Run an automated HERO vs GHOST loop until win/loss or max_turns."""
    state = initialize_game()

    if show_board:
        print("Initial state")
        output(state)
        print()

    turn_count = 0
    stopped_by_user = False
    while not state.game_end and turn_count < max_turns:
        if wait_for_input:
            user_action = input(
                f"Press Enter for turn {turn_count + 1} ({state.turn}) move "
                "or type 'q' to quit: "
            ).strip().lower()
            if user_action in {"q", "quit", "exit"}:
                stopped_by_user = True
                print("Game stopped by user.")
                break

        if state.turn == "HERO":
            best_move, score = minimax_hero_move(state, minimax_depth)
            hero_distance = get_next_move("HERO")
            next_ghost_distance = _distance_for_turn("GHOST1", 0)

            state = move_hero(state, best_move, next_ghost_distance)
            turn_count += 1

            if show_board:
                print(
                    f"Turn {turn_count}: HERO moved to {best_move} "
                    f"(max distance {hero_distance}, heuristic {score})"
                )
                output(state)
                print()
        else:
            state, _ = _step_game_state(
                state,
                minimax_depth,
                ghost_mcts_depth,
                ghost_mcts_iterations,
            )
            turn_count += 1

            if show_board:
                print(
                    f"Turn {turn_count}: GHOST moved"
                )
                output(state)
                print()
        print(f"Turn {turn_count} completed. Current heuristices: {heroistics(state)}")
        print(f"Remaining dots: {state.dots}")

    if state.game_end:
        print(f"Game over. Winner: {state.winner}")
    elif stopped_by_user:
        pass
    else:
        print("Game ended by max_turns limit.")

    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PacMan simulation backend/frontend server")
    parser.add_argument("--api", action="store_true", help="Run Flask API backend")
    parser.add_argument("--host", default="127.0.0.1", help="API host")
    parser.add_argument("--port", type=int, default=5000, help="API port")
    args = parser.parse_args()

    if args.api:
        app = create_app()
        app.run(host=args.host, port=args.port)
    else:
        run_game_loop(max_turns=200, minimax_depth=4, show_board=True)
