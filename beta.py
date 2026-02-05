# ============================================
# Simulation Life 1.0 BETA - MixCode + Mapbox SDK
# ============================================

import os
import io
import json
import random
import threading
import sys

# -----------------------------
# Panda3D Core
# -----------------------------
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    NodePath, Vec3, Texture, PNMImage, loadPrcFileData
)

# -----------------------------
# Networking
# -----------------------------
from panda3d.core import (
    QueuedConnectionManager, QueuedConnectionListener,
    QueuedConnectionReader, ConnectionWriter, NetDatagram
)

# -----------------------------
# VR / OpenXR
# -----------------------------
try:
    from panda3d.core import OpenXRInterface
    OPENXR_AVAILABLE = True
except ImportError:
    OPENXR_AVAILABLE = False

# -----------------------------
# Mapbox SDK
# -----------------------------
from mapbox import Static
from PIL import Image

# -----------------------------
# Config loader
# -----------------------------
def load_itconfig(path="itconfig.json"):
    if not os.path.exists(path):
        return {
            "multiplayer": True,
            "auto-port": True,
            "server": True,
            "mapbox_token": "",  # Вставь свой Mapbox токен
            "mapbox_style": "mapbox/streets-v12",
            "start_lat": 37.7749,
            "start_lon": -122.4194,
            "zoom": 16
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------------
# Mapbox tile loader
# -----------------------------
def get_mapbox_tile(lat, lon, zoom, token, style="mapbox/streets-v12"):
    service = Static(access_token=token)
    response = service.image(style, lon=lon, lat=lat, z=zoom, width=512, height=512)
    if response.status_code == 200:
        img = Image.open(io.BytesIO(response.content))
        return img
    else:
        print(f"[Mapbox] Failed to get tile: {response.status_code}")
        return None

# -----------------------------
# JSON world loader
# -----------------------------
def load_code_json(world, path="Code.JSON/world.json"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for obj in data.get("objects", []):
        node = world.attachNewNode(obj.get("name", "Object"))
        node.setPos(*obj.get("position", [0, 0, 0]))

# -----------------------------
# NetServer / NetClient
# -----------------------------
class NetServer:
    def __init__(self, port):
        self.manager = QueuedConnectionManager()
        self.listener = QueuedConnectionListener(self.manager, 0)
        self.reader = QueuedConnectionReader(self.manager, 0)
        self.writer = ConnectionWriter(self.manager, 0)

        self.port = port
        self.connections = []

        self.socket = self.manager.openTCPServerRendezvous(port, 1000)
        self.listener.addConnection(self.socket)
        print(f"[NET] Server started on port {port}")

    def update(self):
        if self.listener.newConnectionAvailable():
            rendezvous = self.listener.getNewConnection()
            self.reader.addConnection(rendezvous)
            self.connections.append(rendezvous)
            print("[NET] Client connected")

class NetClient:
    def __init__(self, host, port):
        self.manager = QueuedConnectionManager()
        self.reader = QueuedConnectionReader(self.manager, 0)
        self.writer = ConnectionWriter(self.manager, 0)

        self.connection = self.manager.openTCPClientConnection(host, port, 3000)
        if self.connection:
            self.reader.addConnection(self.connection)
            print("[NET] Connected to server")

# -----------------------------
# Main Simulation
# -----------------------------
class SimulationLife(ShowBase):
    def __init__(self):
        super().__init__()
        self.config = load_itconfig()
        self.world = render.attachNewNode("World")

        # --- Mapbox ---
        token = self.config.get("mapbox_token")
        if token:
            tile = get_mapbox_tile(
                self.config.get("start_lat"),
                self.config.get("start_lon"),
                self.config.get("zoom"),
                token,
                self.config.get("mapbox_style")
            )
            if tile:
                # Конвертируем PIL Image в PNMImage для Panda3D
                pnm = PNMImage(tile.width, tile.height)
                tile_rgb = tile.convert("RGB")
                for x in range(tile.width):
                    for y in range(tile.height):
                        r, g, b = tile_rgb.getpixel((x, y))
                        pnm.setXel(x, y, r/255, g/255, b/255)
                tex = Texture()
                tex.load(pnm)
                np = self.world.attachNewNode("MapTile")
                np.setTexture(tex)
                print("[Mapbox] Tile loaded")
        else:
            print("[Mapbox] No token provided")

        # --- Load JSON objects ---
        load_code_json(self.world)

        # --- Multiplayer ---
        self.server = None
        self.client = None
        port = random.randint(20000, 40000)
        if self.config.get("multiplayer"):
            if self.config.get("server"):
                self.server = NetServer(port)
            self.client = NetClient("localhost", port)

        self.taskMgr.add(self.update, "update")

        # --- Camera ---
        self.camera.setPos(0, -40, 20)
        self.camera.lookAt(0, 0, 0)

        print("[SYSTEM] Simulation Life started")

    def update(self, task):
        if self.server:
            self.server.update()
        return task.cont

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app = SimulationLife()
    app.run()
