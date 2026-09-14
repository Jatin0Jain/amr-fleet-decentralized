"""
robot_node.py — P2P WebSocket Network Node
[P2P PERSON] — Each robot runs one of these.

Each robot node:
  - Runs a WebSocket SERVER on its own port (R1→8001, R2→8002, R3→8003)
  - Connects as a CLIENT to all peer ports
  - Broadcasts JSON state every 200ms to all connected peers
  - Calls on_message(sender_id, data) when a message arrives

Usage:
    node = RobotNode(robot_id="R1", port=8001, peers=["ws://localhost:8002", "ws://localhost:8003"])
    asyncio.run(node.run(on_message_callback))
"""

import asyncio
import json
import time
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Callable, Optional

# Reconnect delay when a peer goes offline
RECONNECT_DELAY = 2.0
# How often to broadcast state (seconds)
BROADCAST_INTERVAL = 0.2


class RobotNode:
    """
    P2P WebSocket node for one robot.

    Maintains connections to all peer robots and the dashboard.
    """

    def __init__(self, robot_id: str, port: int, peer_urls: list[str],
                 dashboard_url: str = "ws://localhost:8080"):
        """
        Args:
            robot_id:      e.g. "R1"
            port:          this robot's server port (R1=8001, R2=8002, R3=8003)
            peer_urls:     list of other robots' WebSocket URLs
                           e.g. ["ws://localhost:8002", "ws://localhost:8003"]
            dashboard_url: where to forward state for the dashboard
        """
        self.robot_id = robot_id
        self.port = port
        self.peer_urls = peer_urls
        self.dashboard_url = dashboard_url

        # Active peer connections {url: websocket}
        self._peer_connections: dict[str, Optional[websockets.WebSocketClientProtocol]] = {
            url: None for url in peer_urls
        }
        self._dashboard_conn: Optional[websockets.WebSocketClientProtocol] = None

        # Latest state JSON to broadcast (set externally by sim_runner)
        self._current_state_json: str = ""

        # Callback for incoming messages
        self._on_message: Optional[Callable[[str, dict], None]] = None

        # Peers' latest known states {robot_id: dict}
        self.peer_states: dict[str, dict] = {}

        # Running flag
        self._running: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state_json: str) -> None:
        """Update the JSON state that will be broadcast to peers. Called every tick."""
        self._current_state_json = state_json

    def get_peer_states(self) -> dict[str, dict]:
        """Return the last received state from each peer robot."""
        return dict(self.peer_states)

    def stop(self) -> None:
        """Signal the node to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self, on_message: Callable[[str, dict], None]) -> None:
        """
        Start the node: launch server + connect to peers + broadcast loop.
        All tasks run concurrently via asyncio.gather().
        """
        self._on_message = on_message
        self._running = True

        await asyncio.gather(
            self._serve(),
            self._connect_to_peers(),
            self._broadcast_loop(),
            self._connect_dashboard(),
            return_exceptions=True,  # Don't crash everything if one task fails
        )

    # ------------------------------------------------------------------
    # Server — receives messages from peers
    # ------------------------------------------------------------------

    async def _serve(self) -> None:
        """
        Start WebSocket server. Peers connect here to send us their state.
        Listens on self.port (e.g. 8001 for R1).
        """
        async def _handler(websocket: WebSocketServerProtocol, path: str = "/") -> None:
            try:
                async for raw_message in websocket:
                    try:
                        data = json.loads(raw_message)
                        peer_id = data.get("robot_id", "unknown")
                        self.peer_states[peer_id] = data
                        if self._on_message:
                            self._on_message(peer_id, data)
                    except (json.JSONDecodeError, KeyError):
                        pass  # Malformed message — ignore
            except websockets.exceptions.ConnectionClosed:
                pass

        async with websockets.serve(_handler, "localhost", self.port):
            print(f"[{self.robot_id}] P2P server listening on port {self.port}")
            # Keep server alive until stopped
            while self._running:
                await asyncio.sleep(0.5)

    # ------------------------------------------------------------------
    # Client — connects to peers and maintains connections
    # ------------------------------------------------------------------

    async def _connect_to_peers(self) -> None:
        """
        Connect to all peer robots and maintain those connections.
        Reconnects automatically if a peer goes offline.
        """
        async def _connect_one(url: str) -> None:
            while self._running:
                try:
                    async with websockets.connect(
                        url,
                        ping_interval=5,
                        ping_timeout=10,
                        open_timeout=5,
                    ) as ws:
                        self._peer_connections[url] = ws
                        print(f"[{self.robot_id}] Connected to peer: {url}")
                        # Keep connection alive until it drops
                        while self._running:
                            await asyncio.sleep(BROADCAST_INTERVAL)
                except (OSError, websockets.exceptions.WebSocketException):
                    # Peer is offline — clear connection and retry after delay
                    self._peer_connections[url] = None
                    await asyncio.sleep(RECONNECT_DELAY)
                except Exception:
                    self._peer_connections[url] = None
                    await asyncio.sleep(RECONNECT_DELAY)

        # Connect to each peer concurrently
        tasks = [_connect_one(url) for url in self.peer_urls]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _broadcast_loop(self) -> None:
        """
        Send self._current_state_json to all connected peers every BROADCAST_INTERVAL.
        """
        # Give the server and connections a moment to start up
        await asyncio.sleep(1.0)

        while self._running:
            if self._current_state_json:
                dead_urls = []
                for url, conn in self._peer_connections.items():
                    if conn is not None:
                        try:
                            await conn.send(self._current_state_json)
                        except Exception:
                            # Connection dropped — will reconnect automatically
                            dead_urls.append(url)
                for url in dead_urls:
                    self._peer_connections[url] = None

            await asyncio.sleep(BROADCAST_INTERVAL)

    # ------------------------------------------------------------------
    # Dashboard forwarding
    # ------------------------------------------------------------------

    async def _connect_dashboard(self) -> None:
        """
        Connect to dashboard WebSocket and forward state every tick.
        Handles disconnects gracefully (dashboard might not be open yet).
        """
        await asyncio.sleep(1.0)  # Wait for server startup

        while self._running:
            try:
                async with websockets.connect(
                    self.dashboard_url,
                    ping_interval=10,
                    ping_timeout=20,
                    open_timeout=5,
                ) as ws:
                    self._dashboard_conn = ws
                    print(f"[{self.robot_id}] Connected to dashboard: {self.dashboard_url}")
                    while self._running:
                        if self._current_state_json:
                            try:
                                await ws.send(self._current_state_json)
                            except Exception:
                                break
                        await asyncio.sleep(BROADCAST_INTERVAL)
            except Exception:
                # Dashboard not running yet — retry after delay, no crash
                self._dashboard_conn = None
                await asyncio.sleep(RECONNECT_DELAY)

    async def disconnect(self) -> None:
        """Gracefully close all connections."""
        self._running = False
        for url, conn in self._peer_connections.items():
            if conn:
                try:
                    await conn.close()
                except Exception:
                    pass
        if self._dashboard_conn:
            try:
                await self._dashboard_conn.close()
            except Exception:
                pass
