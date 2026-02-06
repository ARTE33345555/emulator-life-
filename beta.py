# ============================================
# Simulator VR βeta - MyUp Edition
# Anime + VR Life Simulation Prototype
# ============================================

import os, io, json, math
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import Vec3, Texture, PNMImage

# -----------------------------
# Mapbox
# -----------------------------
from mapbox import Static
from PIL import Image

# -----------------------------
# OpenXR check
# -----------------------------
try:
    from panda3d.core import OpenXRInterface
    OPENXR_AVAILABLE = True
except ImportError:
    OPENXR_AVAILABLE = False


# -----------------------------
# CONFIG
# -----------------------------
def load_itconfig(path="itconfig.json"):
    if not os.path.exists(path):
        return {
            "demo_mode": True,
            "vr_strap": "",
            "mapbox_token": "",
            "start_lat": 37.7749,
            "start_lon": -122.4194,
            "zoom": 16
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------
# MAPBOX TILE
# -----------------------------
def get_mapbox_tile(lat, lon, zoom, token):
    service = Static(access_token=token)
    response = service.image(
        "mapbox/streets-v12",
        lon=lon, lat=lat, z=zoom,
        width=512, height=512
    )
    if response.status_code == 200:
        return Image.open(io.BytesIO(response.content))
    return None


# ============================================
# MAIN APP
# ============================================
class SimulatorVR(ShowBase):

    def __init__(self):
        super().__init__()

        print("[MyUp] This simulation was created on this computer.")

        self.config = load_itconfig()
        self.world = render.attachNewNode("World")

        # -------------------------
        # INTRO TEXT (Anime style)
        # -------------------------
        self.intro = OnscreenText(
            text="Welcome to Virtual Reality Simulation Life",
            pos=(0, 0.8),
            scale=0.07
        )

        self.taskMgr.doMethodLater(3, self.remove_intro, "removeIntro")

        # -------------------------
        # FULL VR FLAG
        # -------------------------
        self.full_vr_enabled = self.config.get("vr_strap") == "100%"

        if self.full_vr_enabled and OPENXR_AVAILABLE:
            xr = OpenXRInterface()
            base.openXR.setInterface(xr)
            print("[VR] Full immersion enabled")
        else:
            print("[SYSTEM] Demo / Desktop mode")

        # -------------------------
        # MAPBOX
        # -------------------------
        token = self.config.get("mapbox_token")
        if token:
            tile = get_mapbox_tile(
                self.config["start_lat"],
                self.config["start_lon"],
                self.config["zoom"],
                token
            )

            if tile:
                pnm = PNMImage(tile.width, tile.height)
                rgb = tile.convert("RGB")

                for x in range(tile.width):
                    for y in range(tile.height):
                        r, g, b = rgb.getpixel((x, tile.height-y-1))
                        pnm.setXel(x, y, r/255, g/255, b/255)

                tex = Texture()
                tex.load(pnm)

                plane = self.world.attachNewNode("Map")
                plane.setTexture(tex)

                print("[Mapbox] Map loaded")

        # -------------------------
        # AVATAR
        # -------------------------
        self.avatar = self.world.attachNewNode("Avatar")
        self.avatar.setPos(0, 0, 0)

        # Aura (anime feeling)
        aura = loader.loadModel("models/smiley")
        aura.setScale(0.5)
        aura.setColor(0.3, 0.6, 1, 0.3)
        aura.reparentTo(self.avatar)

        # -------------------------
        # CAMERA
        # -------------------------
        self.camera.setPos(0, -40, 20)
        self.camera.lookAt(self.avatar)

        # -------------------------
        # MOVEMENT (Demo)
        # -------------------------
        self.accept("w", self.move, [0, 1])
        self.accept("s", self.move, [0, -1])
        self.accept("a", self.move, [-1, 0])
        self.accept("d", self.move, [1, 0])

        # -------------------------
        # UPDATE LOOP
        # -------------------------
        self.taskMgr.add(self.update, "update")

    # -------------------------
    def remove_intro(self, task):
        self.intro.destroy()
        return task.done

    # -------------------------
    def move(self, dx, dy):
        self.avatar.setPos(self.avatar, Vec3(dx, dy, 0))

    # -------------------------
    def update(self, task):
        # Slight anime camera motion
        t = task.time
        self.camera.setZ(20 + math.sin(t) * 0.2)
        self.camera.lookAt(self.avatar)
        return task.cont


# ============================================
if __name__ == "__main__":
    app = SimulatorVR()
    app.run()

