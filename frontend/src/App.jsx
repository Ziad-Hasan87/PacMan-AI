import { useEffect, useMemo, useRef, useState } from "react";
import dotImg from "../assets/dot.png";
import ghostImg from "../assets/ghost.png";
import pacmanImg from "../assets/pacman.png";
import wallImg from "../assets/wall.png";

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`);
  }
  return response.json();
}

async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`POST ${path} failed: ${response.status} ${text}`);
  }
  return response.json();
}

function cellClass(ch) {
  if (ch === "#") return "cell wall";
  if (ch === "H") return "cell hero";
  if (ch === "G") return "cell ghost";
  if (ch === "o") return "cell pellet";
  return "cell floor";
}

function tileOrientation(row, col, seed) {
  const hash = Math.abs(((row + 1) * 73856093) ^ ((col + 1) * 19349663) ^ (seed * 83492791));
  return {
    rotate: (hash % 4) * 90,
    flip: hash % 2 === 0 ? 1 : -1,
  };
}

function wallOutlineShadow(rows, row, col) {
  if (rows[row]?.[col] !== "#") {
    return "none";
  }

  const isWall = (r, c) => (
    r >= 0
    && r < rows.length
    && c >= 0
    && c < rows[r].length
    && rows[r][c] === "#"
  );

  const navy = "rgba(20, 46, 92, 0.98)";
  const edges = [];

  if (!isWall(row - 1, col)) edges.push(`inset 0 3px 0 0 ${navy}`);
  if (!isWall(row + 1, col)) edges.push(`inset 0 -3px 0 0 ${navy}`);
  if (!isWall(row, col - 1)) edges.push(`inset 3px 0 0 0 ${navy}`);
  if (!isWall(row, col + 1)) edges.push(`inset -3px 0 0 0 ${navy}`);

  return edges.length ? edges.join(", ") : "none";
}

function cellStyle(ch, row, col, rows) {
  let baseImage = "none";
  let overlayImage = "none";

  if (ch === "#") {
    baseImage = `url(${wallImg})`;
  }

  if (ch === "H") overlayImage = `url(${pacmanImg})`;
  if (ch === "G") overlayImage = `url(${ghostImg})`;
  if (ch === "o") overlayImage = `url(${dotImg})`;

  const style = {
    "--tile-base": baseImage,
    "--tile-overlay": overlayImage,
  };

  if (baseImage !== "none") {
    const orientation = tileOrientation(row, col, ch === "#" ? 11 : 29);
    style["--tile-rotation"] = `${orientation.rotate}deg`;
    style["--tile-flip"] = String(orientation.flip);
  }

  if (ch === "#") {
    style["--wall-outline-shadow"] = wallOutlineShadow(rows, row, col);
  }

  return style;
}

function normalizeMazeRows(layout) {
  return (layout || []).map((row) => row.replace(/[HG]/g, " "));
}

function toVisualState(data) {
  if (!data) {
    return null;
  }

  return {
    maze_layout: normalizeMazeRows(data.maze_layout),
    hero: data.hero,
    ghosts: data.ghosts,
  };
}

function buildLinearPath(start, end) {
  if (!start || !end) {
    return [];
  }

  const [sr, sc] = start;
  const [er, ec] = end;
  if (sr === er && sc === ec) {
    return [start];
  }

  const path = [start];
  if (sr === er) {
    const step = ec > sc ? 1 : -1;
    for (let c = sc + step; c !== ec + step; c += step) {
      path.push([sr, c]);
    }
    return path;
  }

  const step = er > sr ? 1 : -1;
  for (let r = sr + step; r !== er + step; r += step) {
    path.push([r, sc]);
  }

  return path;
}

function displayCharAt(rows, visual, row, col) {
  const hero = visual?.hero;
  const ghost = visual?.ghosts?.[0];

  if (hero && hero[0] === row && hero[1] === col) {
    return "H";
  }
  if (ghost && ghost[0] === row && ghost[1] === col) {
    return "G";
  }

  return rows[row]?.[col] || " ";
}

export default function App() {
  const [game, setGame] = useState(null);
  const [visual, setVisual] = useState(null);
  const [movingActor, setMovingActor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tileSize, setTileSize] = useState(16);
  const [floorRotation] = useState(() => [0, 90, 180, 270][Math.floor(Math.random() * 4)]);
  const [floorFlip] = useState(() => (Math.random() > 0.5 ? 1 : -1));
  const boardShellRef = useRef(null);
  const gameRef = useRef(null);
  const timersRef = useRef([]);
  const animationTokenRef = useRef(0);

  const [minimaxDepth, setMinimaxDepth] = useState(4);
  const [ghostMctsDepth, setGhostMctsDepth] = useState(8);
  const [ghostMctsIterations, setGhostMctsIterations] = useState(200);
  const [thirst, setThirst] = useState(1);
  const [commitment, setCommitment] = useState(1);
  const [safety, setSafety] = useState(1);

  useEffect(() => {
    void refreshState();
  }, []);

  useEffect(() => () => {
    timersRef.current.forEach((timerId) => clearTimeout(timerId));
    timersRef.current = [];
  }, []);

  function clearPendingAnimationTimers() {
    timersRef.current.forEach((timerId) => clearTimeout(timerId));
    timersRef.current = [];
  }

  function syncHeuristicMultipliers(nextData) {
    const multipliers = nextData?.hero_multipliers;
    if (!multipliers) {
      return;
    }

    const parsedThirst = Number(multipliers.thirst);
    const parsedCommitment = Number(multipliers.commitment);
    const parsedSafety = Number(multipliers.safety);

    if (Number.isFinite(parsedThirst)) setThirst(parsedThirst);
    if (Number.isFinite(parsedCommitment)) setCommitment(parsedCommitment);
    if (Number.isFinite(parsedSafety)) setSafety(parsedSafety);
  }

  function pushGameData(nextData) {
    syncHeuristicMultipliers(nextData);
    const previousData = gameRef.current;
    setGame(nextData);

    if (!previousData) {
      setVisual(toVisualState(nextData));
      gameRef.current = nextData;
      setMovingActor(null);
      return;
    }

    const actor = nextData?.last_transition?.actor;
    const previousVisual = toVisualState(previousData);
    const nextVisual = toVisualState(nextData);

    if (!actor || !previousVisual || !nextVisual) {
      setVisual(nextVisual);
      gameRef.current = nextData;
      setMovingActor(null);
      return;
    }

    const path = actor === "HERO"
      ? buildLinearPath(previousData.hero, nextData.hero)
      : buildLinearPath(previousData.ghosts?.[0], nextData.ghosts?.[0]);

    if (path.length <= 1) {
      setVisual(nextVisual);
      gameRef.current = nextData;
      setMovingActor(null);
      return;
    }

    clearPendingAnimationTimers();
    const token = animationTokenRef.current + 1;
    animationTokenRef.current = token;
    gameRef.current = nextData;
    setMovingActor(actor);
    setVisual(previousVisual);

    const stepMs = 240;
    path.slice(1).forEach((position, index) => {
      const timerId = setTimeout(() => {
        if (animationTokenRef.current !== token) {
          return;
        }

        if (actor === "HERO") {
          setVisual({
            maze_layout: nextVisual.maze_layout,
            hero: position,
            ghosts: nextVisual.ghosts,
          });
        } else {
          setVisual({
            maze_layout: nextVisual.maze_layout,
            hero: nextVisual.hero,
            ghosts: [position],
          });
        }

        if (index === path.length - 2) {
          setMovingActor(null);
        }
      }, stepMs * (index + 1));

      timersRef.current.push(timerId);
    });

    const finalTimer = setTimeout(() => {
      if (animationTokenRef.current !== token) {
        return;
      }
      setVisual(nextVisual);
      setMovingActor(null);
    }, stepMs * path.length + 10);
    timersRef.current.push(finalTimer);
  }

  async function refreshState() {
    setLoading(true);
    setError("");
    try {
      const data = await apiGet("/api/state");
      pushGameData(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function startGame() {
    setLoading(true);
    setError("");
    try {
      clearPendingAnimationTimers();
      const data = await apiPost("/api/start", {
        minimax_depth: Number(minimaxDepth),
        ghost_mcts_depth: Number(ghostMctsDepth),
        ghost_mcts_iterations: Number(ghostMctsIterations),
        thirst: Number(thirst),
        commitment: Number(commitment),
        safety: Number(safety),
      });
      pushGameData(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function signal(action) {
    setLoading(true);
    setError("");
    try {
      const data = await apiPost("/api/signal", {
        action,
        thirst: Number(thirst),
        commitment: Number(commitment),
        safety: Number(safety),
      });
      pushGameData(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  const boardRows = useMemo(() => visual?.maze_layout || [], [visual]);
  const rowCount = boardRows.length;
  const colCount = boardRows[0]?.length || 0;
  const canControl = !!game && !game.game_end && !game.stopped_by_user;
  const statusTone = game?.game_end ? "finished" : game?.stopped_by_user ? "paused" : "running";

  useEffect(() => {
    const shell = boardShellRef.current;
    if (!shell || rowCount === 0 || colCount === 0) {
      return;
    }

    const updateSize = () => {
      const availableWidth = shell.clientWidth - 24;
      const availableHeight = shell.clientHeight - 24;
      if (availableWidth <= 0 || availableHeight <= 0) {
        return;
      }

      const byWidth = Math.floor(availableWidth / colCount);
      const byHeight = Math.floor(availableHeight / rowCount);
      const next = Math.max(8, Math.min(22, Math.min(byWidth, byHeight)));
      setTileSize(next);
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(shell);
    window.addEventListener("resize", updateSize);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateSize);
    };
  }, [rowCount, colCount]);

  return (
    <div className="app">
      <div className="backdrop-orb orb-a" />
      <div className="backdrop-orb orb-b" />

      <header className="header panel">
        <div>
          <p className="kicker">Agent Dashboard</p>
          <h1>PacMan Simulation Control Room</h1>
          <p className="subhead">Python backend computes turns. React sends continue/quit signals and renders live maze JSON.</p>
        </div>
        <div className={`status-pill ${statusTone}`}>
          {game?.game_end ? `Winner: ${game.winner || "None"}` : game?.stopped_by_user ? "Stopped" : "Running"}
        </div>
      </header>

      <section className="layout">
        <section className="panel board-panel">
          <div className="board-title-row">
            <h2>Maze Feed</h2>
            {loading && <span className="loading-chip">Syncing...</span>}
          </div>
          <div className="board-shell" ref={boardShellRef}>
            <div
              className="board"
              style={{
                "--tile-size": `${tileSize}px`,
                "--floor-rotation": `${floorRotation}deg`,
                "--floor-flip": String(floorFlip),
              }}
            >
              {boardRows.map((row, r) => (
                <div key={r} className="row">
                  {[...row].map((_, c) => {
                    const displayChar = displayCharAt(boardRows, visual, r, c);
                    const movingClass = displayChar === "H" && movingActor === "HERO"
                      ? " moving-hero"
                      : displayChar === "G" && movingActor === "GHOST"
                        ? " moving-ghost"
                        : "";

                    return (
                      <span
                        key={`${r}-${c}`}
                        className={`${cellClass(displayChar)}${movingClass}`}
                        style={cellStyle(displayChar, r, c, boardRows)}
                        title={`(${r}, ${c}) ${displayChar === " " ? "floor" : displayChar}`}
                        aria-label={`${displayChar === " " ? "floor" : displayChar} at row ${r}, col ${c}`}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className="right-rail">
          <section className="panel controls">
            <div className="controls-title-row">
              <h2>Simulation Settings</h2>
              <span className="muted">Tune search and heuristic weights before starting or resetting.</span>
            </div>

            <div className="config-grid">
              <label>
                HERO Minimax Depth
                <input
                  type="number"
                  min="1"
                  value={minimaxDepth}
                  onChange={(e) => setMinimaxDepth(e.target.value)}
                />
              </label>
              <label>
                Ghost MCTS Depth
                <input
                  type="number"
                  min="1"
                  value={ghostMctsDepth}
                  onChange={(e) => setGhostMctsDepth(e.target.value)}
                />
              </label>
              <label>
                Ghost MCTS Iterations
                <input
                  type="number"
                  min="1"
                  value={ghostMctsIterations}
                  onChange={(e) => setGhostMctsIterations(e.target.value)}
                />
              </label>
              <label className="slider-control">
                Thirst
                <div className="slider-row">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="0.5"
                    value={thirst}
                    onChange={(e) => setThirst(Number(e.target.value))}
                  />
                  <output>{thirst.toFixed(1)}</output>
                </div>
                <small>Higher value boosts score as dots become scarce.</small>
              </label>
              <label className="slider-control">
                Commitment
                <div className="slider-row">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="0.5"
                    value={commitment}
                    onChange={(e) => setCommitment(Number(e.target.value))}
                  />
                  <output>{commitment.toFixed(1)}</output>
                </div>
                <small>Higher value increases distance-to-dots contribution.</small>
              </label>
              <label className="slider-control">
                Safety
                <div className="slider-row">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="0.5"
                    value={safety}
                    onChange={(e) => setSafety(Number(e.target.value))}
                  />
                  <output>{safety.toFixed(1)}</output>
                </div>
                <small>Higher value increases ghost-proximity penalty.</small>
              </label>
            </div>

            <div className="buttons">
              <button className="primary" onClick={startGame} disabled={loading}>Start / Reset</button>
              <button className="accent" onClick={() => signal("continue")} disabled={loading || !canControl}>
                Continue
              </button>
              <button className="danger" onClick={() => signal("quit")} disabled={loading || !canControl}>
                Quit
              </button>
              <button className="ghost" onClick={refreshState} disabled={loading}>Refresh</button>
            </div>

            {error && <div className="error">{error}</div>}
          </section>

          <section className="metrics-grid">
            <article className="panel metric-card">
              <span className="metric-label">Turn</span>
              <strong>{game?.turn_count ?? "-"}</strong>
              <small>{game?.turn || "Unknown"}</small>
            </article>
            <article className="panel metric-card">
              <span className="metric-label">Dots Remaining</span>
              <strong>{game?.dots_remaining ?? "-"}</strong>
              <small>Objective pellets left</small>
            </article>
            <article className="panel metric-card">
              <span className="metric-label">Hero Heuristic</span>
              <strong>{game?.hero_heuristic ?? "-"}</strong>
              <small>Higher is better for hero</small>
            </article>
            <article className="panel metric-card">
              <span className="metric-label">Ghost Heuristic</span>
              <strong>{game?.ghost_heuristic ?? "-"}</strong>
              <small>Higher is better for ghost</small>
            </article>
          </section>

          <section className="panel status">
            <h2>Live Status</h2>
            {game ? (
              <div className="status-grid">
                <div className="status-row"><span>Current Turn</span><strong>{game.turn}</strong></div>
                <div className="status-row"><span>Game End</span><strong>{String(game.game_end)}</strong></div>
                <div className="status-row"><span>Winner</span><strong>{game.winner || "None"}</strong></div>
                <div className="status-row"><span>Stopped By User</span><strong>{String(game.stopped_by_user)}</strong></div>
                <div className="status-row wide">
                  <span>Last Transition</span>
                  <strong>
                    {game.last_transition
                      ? `${game.last_transition.actor} moved to [${game.last_transition.move?.join(", ")}]`
                      : "None"}
                  </strong>
                </div>
              </div>
            ) : (
              <p>No state loaded.</p>
            )}

            <div className="legend">
              <h3>Legend</h3>
              <div className="legend-grid">
                <span><i className="dot" style={{ backgroundImage: `url(${wallImg})` }} /> Wall</span>
                <span><i className="dot" style={{ backgroundImage: `url(${pacmanImg})` }} /> Hero</span>
                <span><i className="dot" style={{ backgroundImage: `url(${ghostImg})` }} /> Ghost</span>
                <span><i className="dot" style={{ backgroundImage: `url(${dotImg})` }} /> Pellet</span>
              </div>
            </div>
          </section>
        </aside>
      </section>
    </div>
  );
}
