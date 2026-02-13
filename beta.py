# ============================================
# Simulator VR βeta - MyUp Edition
# Anime + VR Life Simulation Prototype
# OPENXR VR READY
# ============================================

import os
import io
import json
import math
import random
import sys
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectLabel, DirectWaitBar
from panda3d.core import *
from mapbox import Static
from PIL import Image
from direct.interval.LerpInterval import LerpPosInterval, LerpScaleInterval, LerpHprInterval
from direct.interval.IntervalGlobal import Sequence, Parallel, Func
from direct.task import Task

# -----------------------------
# OpenXR імпорт та перевірка
# -----------------------------
try:
    from panda3d.core import OpenXRInterface
    from panda3d.core import VRSystem
    from panda3d.core import VrpnAnalog, VrpnButton, VrpnTracker
    OPENXR_AVAILABLE = True
    print("[VR] OpenXR підтримку знайдено")
except ImportError as e:
    OPENXR_AVAILABLE = False
    print(f"[VR] OpenXR не доступний: {e}")

# -----------------------------
# CONFIG
# -----------------------------
def load_itconfig(path="itconfig.json"):
    default_config = {
        "demo_mode": True,
        "vr_strap": "100%",  # Змінено на 100% для VR
        "vr_handedness": "right",  # права/ліва рука
        "vr_height": 1.7,  # зріст користувача в метрах
        "vr_snap_turn": 45,  # градуси для повороту
        "vr_comfort_vignette": True,  # затемнення по краях для комфорту
        "mapbox_token": "",
        "start_lat": 37.7749,
        "start_lon": -122.4194,
        "zoom": 16,
        "sound_enabled": True,
        "music_volume": 0.7,
        "effects_volume": 0.8,
        "anime_effects": True  # аніме-ефекти (іскри, аура)
    }
    
    if not os.path.exists(path):
        print(f"[CONFIG] Конфігурацію не знайдено, створюю стандартну {path}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
        return default_config
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        print(f"[CONFIG] Помилка завантаження: {e}")
        return default_config

# ============================================
# VR SYSTEM CLASS
# ============================================
class VRSystemManager:
    """Менеджер VR системи з підтримкою OpenXR"""
    
    def __init__(self, base):
        self.base = base
        self.config = load_itconfig()
        self.vr_initialized = False
        self.vr_controllers = {}
        self.vr_hmd = None
        self.vr_origin = render.attachNewNode("VR_Origin")
        
        # Трекінг рук
        self.left_hand = self.vr_origin.attachNewNode("LeftHand")
        self.right_hand = self.vr_origin.attachNewNode("RightHand")
        self.head = self.vr_origin.attachNewNode("Head")
        
        # Моделі для рук (аніме-стиль)
        self.hand_models = {}
        
        if self.config.get("vr_strap") == "100%" and OPENXR_AVAILABLE:
            self.init_vr()
    
    def init_vr(self):
        """Ініціалізація OpenXR"""
        try:
            print("[VR] Ініціалізація OpenXR...")
            
            # Створюємо інтерфейс OpenXR
            self.xr_interface = OpenXRInterface()
            
            # Налаштовуємо параметри
            self.xr_interface.set_require_hand_tracking(True)  # Потрібне відстеження рук
            self.xr_interface.set_require_stage_bounds(True)   # Потрібні границі кімнати
            
            # Ініціалізуємо VR систему
            if self.base.openXR.set_interface(self.xr_interface):
                self.base.openXR.set_vr_mode(True)
                self.vr_initialized = True
                
                # Налаштовуємо камеру для VR
                self.setup_vr_camera()
                
                # Завантажуємо моделі для рук
                self.load_hand_models()
                
                # Налаштовуємо контролери
                self.setup_controllers()
                
                print("[VR] OpenXR успішно ініціалізовано!")
            else:
                print("[VR] Не вдалося встановити інтерфейс OpenXR")
                
        except Exception as e:
            print(f"[VR] Помилка ініціалізації: {e}")
            self.vr_initialized = False
    
    def setup_vr_camera(self):
        """Налаштування VR камери"""
        # Встановлюємо камеру для VR
        self.base.camera.reparentTo(self.head)
        self.base.camera.setPos(0, 0, 0)
        
        # Налаштовуємо параметри відображення
        self.base.cameraLens.setFov(90)  # Типове поле зору для VR
        self.base.cameraLens.setNearFar(0.1, 1000)
        
        print("[VR] Камеру налаштовано")
    
    def load_hand_models(self):
        """Завантаження аніме-моделей для рук"""
        try:
            # Спроба завантажити моделі рук
            hand_model_path = "models/anime_hand"
            if os.path.exists(hand_model_path + ".egg") or os.path.exists(hand_model_path + ".bam"):
                for hand in ['left', 'right']:
                    model = self.base.loader.loadModel(hand_model_path)
                    model.reparentTo(self.left_hand if hand == 'left' else self.right_hand)
                    model.setScale(0.1)
                    
                    # Аніме-ефекти для рук
                    if self.config.get("anime_effects", True):
                        self.add_anime_effects(model, hand)
                    
                    self.hand_models[hand] = model
                    print(f"[VR] Завантажено модель для {hand} руки")
            else:
                # Створюємо прості моделі, якщо немає файлів
                self.create_fallback_hand_models()
                
        except Exception as e:
            print(f"[VR] Помилка завантаження моделей рук: {e}")
            self.create_fallback_hand_models()
    
    def create_fallback_hand_models(self):
        """Створення простих моделей для рук"""
        for hand_name, hand_node in [('left', self.left_hand), ('right', self.right_hand)]:
            # Долоня
            palm = self.base.loader.loadModel("models/box")
            palm.setScale(0.08, 0.1, 0.03)
            palm.setColor(1, 0.8, 0.6, 1)
            palm.reparentTo(hand_node)
            
            # Пальці (прості кубики)
            for i in range(5):
                finger = self.base.loader.loadModel("models/box")
                finger.setScale(0.02, 0.02, 0.06)
                finger.setPos(0.03 * i - 0.06, 0, 0.05)
                finger.setColor(1, 0.8, 0.6, 1)
                finger.reparentTo(hand_node)
            
            # Аніме-аура
            aura = self.base.loader.loadModel("models/sphere")
            aura.setScale(0.15)
            aura.setColor(0.5, 0.8, 1, 0.3)
            aura.setTransparency(TransparencyAttrib.MAlpha)
            aura.reparentTo(hand_node)
            
            self.hand_models[hand_name] = hand_node
    
    def add_anime_effects(self, model, hand):
        """Додавання аніме-ефектів до рук"""
        # Аура навколо руки
        aura = self.base.loader.loadModel("models/sphere")
        aura.setScale(0.2)
        aura.setColor(0.3, 0.6, 1, 0.2)
        aura.setTransparency(TransparencyAttrib.MAlpha)
        aura.reparentTo(model)
        
        # Частинки, що світяться
        particles = ParticleSystem()
        particles.setRenderMode(ParticleSystem.PR_POINT)
        particles.setSpawnType(ParticleSystem.SPT_GENERIC)
        particles.setPoolSize(20)
        # ... налаштування частинок
        
        # Анімація плавання
        taskMgr.add(self.animate_hand_aura, f"animate_hand_{hand}")
    
    def animate_hand_aura(self, task):
        """Анімація аури навколо рук"""
        if hand in self.hand_models:
            t = task.time
            aura = self.hand_models[hand].find("**/aura")
            if aura:
                aura.setColor(0.3 + math.sin(t) * 0.1, 
                            0.6 + math.cos(t * 1.3) * 0.1,
                            1, 0.2)
        return task.cont
    
    def setup_controllers(self):
        """Налаштування VR контролерів"""
        if not self.vr_initialized:
            return
        
        try:
            # Отримуємо контролери
            controllers = self.base.openXR.get_controllers()
            
            for i, controller in enumerate(controllers):
                # Визначаємо, яка це рука
                handedness = controller.get_handedness()
                
                if handedness == OpenXRInterface.HC_left:
                    hand_node = self.left_hand
                    hand_name = "left"
                else:
                    hand_node = self.right_hand
                    hand_name = "right"
                
                # Прив'язуємо контролер до руки
                controller.reparentTo(hand_node)
                
                # Налаштовуємо кнопки
                self.setup_controller_buttons(controller, hand_name)
                
                self.vr_controllers[hand_name] = controller
                print(f"[VR] Контролер для {hand_name} руки налаштовано")
                
        except Exception as e:
            print(f"[VR] Помилка налаштування контролерів: {e}")
    
    def setup_controller_buttons(self, controller, hand):
        """Налаштування кнопок контролера"""
        
        # Кнопка Trigger
        controller.button_trigger.pressed = lambda: self.on_trigger_press(hand)
        controller.button_trigger.released = lambda: self.on_trigger_release(hand)
        
        # Кнопка Grip
        controller.button_grip.pressed = lambda: self.on_grip_press(hand)
        controller.button_grip.released = lambda: self.on_grip_release(hand)
        
        # Кнопка Menu
        controller.button_menu.pressed = lambda: self.on_menu_press(hand)
        
        # Джойстик
        controller.joy_x_changed = lambda x: self.on_joystick_move(hand, x, controller.joy_y)
        controller.joy_y_changed = lambda y: self.on_joystick_move(hand, controller.joy_x, y)
    
    def on_trigger_press(self, hand):
        """Обробка натискання тригера"""
        print(f"[VR] Trigger pressed on {hand} hand")
        
        # Візуальний ефект
        if hand in self.hand_models:
            self.hand_models[hand].setColorScale(0.8, 0.8, 1, 1)
            
            # Аніме-ефект (іскри)
            if self.config.get("anime_effects", True):
                self.create_spark_effect(hand)
    
    def on_trigger_release(self, hand):
        """Обробка відпускання тригера"""
        if hand in self.hand_models:
            self.hand_models[hand].setColorScale(1, 1, 1, 1)
    
    def on_grip_press(self, hand):
        """Обробка натискання Grip"""
        print(f"[VR] Grip pressed on {hand} hand")
        # Тут можна додати захоплення об'єктів
    
    def on_grip_release(self, hand):
        """Обробка відпускання Grip"""
        pass
    
    def on_menu_press(self, hand):
        """Обробка натискання Menu"""
        print(f"[VR] Menu pressed on {hand} hand")
        # Відкриваємо меню
        self.base.show_pause_menu()
    
    def on_joystick_move(self, hand, x, y):
        """Обробка руху джойстика"""
        if hand == 'left':
            # Лівий джойстик для переміщення
            self.base.move_vr(x, y)
        else:
            # Правий джойстик для повороту
            if abs(x) > 0.7:  # Поріг для повороту
                self.base.rotate_vr(x)
    
    def create_spark_effect(self, hand):
        """Створення аніме-ефекту іскор"""
        # Створюємо частинки
        particles = ParticleSystem()
        particles.setRenderMode(ParticleSystem.PR_POINT)
        particles.setSpawnType(ParticleSystem.SPT_GENERIC)
        particles.setPoolSize(50)
        particles.setLifespan(0.5)
        particles.setEmissionRate(100)
        # ... додаткові налаштування
        
        # Розміщуємо на руці
        if hand in self.hand_models:
            particles.reparentTo(self.hand_models[hand])
            
            # Автоматичне видалення через 1 секунду
            taskMgr.doMethodLater(1, lambda t: particles.removeNode(), "remove_sparks")
    
    def update(self, task):
        """Оновлення VR системи"""
        if not self.vr_initialized:
            return task.cont
        
        # Оновлюємо позиції рук з OpenXR
        try:
            # Отримуємо позиції трекінгу
            for hand_name, controller in self.vr_controllers.items():
                if hand_name == 'left':
                    self.left_hand.setPos(controller.getPos())
                    self.left_hand.setHpr(controller.getHpr())
                else:
                    self.right_hand.setPos(controller.getPos())
                    self.right_hand.setHpr(controller.getHpr())
            
            # Оновлюємо позицію голови
            if self.base.openXR.get_hmd():
                self.head.setPos(self.base.openXR.get_hmd().getPos())
                self.head.setHpr(self.base.openXR.get_hmd().getHpr())
                
        except Exception as e:
            # Ігноруємо помилки трекінгу
            pass
        
        return task.cont

# ============================================
# LOADING SCREEN (VR сумісний)
# ============================================
class LoadingScreen:
    def __init__(self, base):
        self.base = base
        self.loading_complete = False
        self.current_progress = 0
        
        # Визначаємо, чи ми у VR режимі
        self.vr_mode = base.vr_manager.vr_initialized if hasattr(base, 'vr_manager') else False
        
        if self.vr_mode:
            # VR-сумісний екран завантаження
            self.setup_vr_loading()
        else:
            # Звичайний 2D екран
            self.setup_2d_loading()
        
        # Починаємо завантаження
        base.taskMgr.add(self.update_progress, "loading_progress")
    
    def setup_vr_loading(self):
        """Налаштування VR-сумісного екрану завантаження"""
        # Створюємо 3D об'єкти в просторі
        self.loading_root = render.attachNewNode("LoadingScreen")
        self.loading_root.setPos(self.base.camera.getPos() + Vec3(0, 10, 0))
        self.loading_root.lookAt(self.base.camera)
        
        # Текст в 3D
        self.logo_text = TextNode('logo')
        self.logo_text.setText("⚡ SAO VR ⚡")
        self.logo_text.setFont(loader.loadFont("cmss12"))
        self.logo_node = self.loading_root.attachNewNode(self.logo_text)
        self.logo_node.setScale(2)
        self.logo_node.setPos(-5, 0, 5)
        
        # Прогрес-бар в 3D
        self.progress_bar = loader.loadModel("models/box")
        self.progress_bar.setScale(10, 0.5, 0.5)
        self.progress_bar.setColor(0, 0.5, 1, 1)
        self.progress_bar.setPos(-5, 0, 2)
        self.progress_bar.reparentTo(self.loading_root)
        
        # Фон
        background = loader.loadModel("models/box")
        background.setScale(12, 0.1, 8)
        background.setColor(0, 0, 0, 0.8)
        background.setPos(-5, -1, 4)
        background.reparentTo(self.loading_root)
    
    def setup_2d_loading(self):
        """Звичайний 2D екран завантаження"""
        self.frame = DirectFrame(frameColor=(0, 0, 0, 1), frameSize=(-1, 1, -1, 1))
        
        self.logo = OnscreenText(text="⚡ SAO VR ⚡", style=1, fg=(1, 0.5, 0.8, 1),
                                pos=(0, 0.6), scale=0.15)
        self.logo.reparentTo(self.frame)
        
        self.progress_bar = DirectWaitBar(value=0, range=100, barColor=(0.3, 0.6, 1, 1),
                                         pos=(0, 0, 0.1), scale=(0.5, 0, 0.05),
                                         parent=self.frame)
        
        self.progress_text = OnscreenText(text="0%", style=1, fg=(1, 1, 1, 1),
                                         pos=(0, 0), scale=0.05)
        self.progress_text.reparentTo(self.frame)
    
    def update_progress(self, task):
        self.current_progress += random.uniform(0.5, 2)
        
        if self.current_progress >= 100:
            self.current_progress = 100
            if hasattr(self, 'progress_bar'):
                if not self.vr_mode:
                    self.progress_bar['value'] = self.current_progress
                    self.progress_text.setText(f"{int(self.current_progress)}%")
            
            if not hasattr(self, 'finish_scheduled'):
                self.finish_scheduled = True
                self.base.taskMgr.doMethodLater(0.5, self.finish_loading, "finishLoading")
            
            return task.done
        
        if hasattr(self, 'progress_bar'):
            if not self.vr_mode:
                self.progress_bar['value'] = self.current_progress
                self.progress_text.setText(f"{int(self.current_progress)}%")
        
        return task.cont
    
    def finish_loading(self, task):
        self.loading_complete = True
        
        if self.vr_mode and hasattr(self, 'loading_root'):
            self.loading_root.removeNode()
        elif hasattr(self, 'frame'):
            self.frame.destroy()
        
        self.base.taskMgr.doMethodLater(0.1, self.show_main_menu, "showMenu")
        return task.done
    
    def show_main_menu(self, task):
        MainMenu(self.base)
        return task.done

# ============================================
# MAIN MENU (VR Ready)
# ============================================
class MainMenu:
    def __init__(self, base):
        self.base = base
        self.vr_mode = base.vr_manager.vr_initialized if hasattr(base, 'vr_manager') else False
        
        if self.vr_mode:
            self.setup_vr_menu()
        else:
            self.setup_2d_menu()
    
    def setup_vr_menu(self):
        """VR-сумісне меню в 3D просторі"""
        self.menu_root = render.attachNewNode("VRMenu")
        self.menu_root.setPos(self.base.camera.getPos() + Vec3(0, 5, 0))
        self.menu_root.setHpr(0, 0, 0)
        
        # Заголовок
        title_text = TextNode('title')
        title_text.setText("☆ SAO VR Simulator ☆")
        title_text.setFont(loader.loadFont("cmss12"))
        title_node = self.menu_root.attachNewNode(title_text)
        title_node.setScale(0.5)
        title_node.setPos(-4, 0, 2)
        
        # Кнопки в 3D
        button_positions = [(0, 0, 1), (0, 0, 0), (0, 0, -1), (0, 0, -2)]
        button_labels = ["Start VR", "Options", "Controls", "Exit"]
        button_commands = [self.start_vr, self.show_options, self.show_controls, self.exit_game]
        
        self.buttons = []
        for i, (pos, label, cmd) in enumerate(zip(button_positions, button_labels, button_commands)):
            btn_root = self.menu_root.attachNewNode(f"Button_{i}")
            btn_root.setPos(pos[0], pos[1], pos[2])
            
            # Фон кнопки
            bg = loader.loadModel("models/box")
            bg.setScale(2, 0.2, 0.5)
            bg.setColor(0.2, 0.2, 0.5, 0.8)
            bg.reparentTo(btn_root)
            
            # Текст
            btn_text = TextNode('button_text')
            btn_text.setText(label)
            btn_text.setFont(loader.loadFont("cmss12"))
            btn_node = btn_root.attachNewNode(btn_text)
            btn_node.setScale(0.3)
            btn_node.setPos(-0.8, 0.1, 0)
            
            self.buttons.append({
                'root': btn_root,
                'bg': bg,
                'command': cmd,
                'original_scale': 1
            })
    
    def setup_2d_menu(self):
        """Звичайне 2D меню"""
        self.frame = DirectFrame(frameColor=(0, 0, 0, 0.9), frameSize=(-1, 1, -1, 1))
        
        self.title = OnscreenText(text="☆ SAO VR Simulator ☆", style=1,
                                 fg=(1, 0.7, 0.2, 1), pos=(0, 0.8), scale=0.12)
        self.title.reparentTo(self.frame)
        
        button_style = {'scale': 0.08, 'frameColor': (0.2, 0.2, 0.5, 0.8),
                       'text_fg': (1, 1, 1, 1)}
        
        self.start_btn = DirectButton(text="▶ Start VR", pos=(0, 0, 0.4),
                                      command=self.start_vr, **button_style)
        self.start_btn.reparentTo(self.frame)
        
        self.options_btn = DirectButton(text="⚙ Options", pos=(0, 0, 0.2),
                                        command=self.show_options, **button_style)
        self.options_btn.reparentTo(self.frame)
        
        self.controls_btn = DirectButton(text="🎮 Controls", pos=(0, 0, 0),
                                         command=self.show_controls, **button_style)
        self.controls_btn.reparentTo(self.frame)
        
        self.exit_btn = DirectButton(text="✖ Exit", pos=(0, 0, -0.2),
                                      command=self.exit_game, **button_style)
        self.exit_btn.reparentTo(self.frame)
    
    def start_vr(self):
        """Запуск VR симуляції"""
        if self.vr_mode and hasattr(self, 'menu_root'):
            self.menu_root.removeNode()
        elif hasattr(self, 'frame'):
            self.frame.destroy()
        
        self.base.start_simulation()
    
    def show_options(self):
        print("[MENU] Options")
    
    def show_controls(self):
        print("[MENU] Controls")
    
    def exit_game(self):
        self.base.userExit()

# ============================================
# VR SIMULATOR
# ============================================
class SimulatorVR(ShowBase):
    def __init__(self):
        super().__init__()
        
        # Налаштування вікна
        props = WindowProperties()
        props.setTitle("SAO VR Simulator - MyUp Edition")
        props.setSize(1920, 1080)
        self.win.requestProperties(props)
        
        self.config = load_itconfig()
        self.world = render.attachNewNode("World")
        self.simulation_running = False
        
        # Створюємо VR менеджер
        self.vr_manager = VRSystemManager(self)
        
        # Створюємо директорії
        self.create_directories()
        
        # Запускаємо завантаження
        LoadingScreen(self)
    
    def create_directories(self):
        dirs = ["sounds", "models", "saves", "screenshots", "shaders"]
        for dir_name in dirs:
            if not os.path.exists(dir_name):
                os.makedirs(dir_name)
                print(f"[SYSTEM] Створено директорію: {dir_name}")
    
    def start_simulation(self):
        """Запуск VR симуляції"""
        self.simulation_running = True
        print("[MyUp] VR Simulation started.")
        
        # VR режим
        if self.vr_manager.vr_initialized:
            self.start_vr_mode()
        else:
            self.start_desktop_mode()
        
        # Створюємо світ
        self.create_world()
        
        # Запускаємо оновлення
        self.taskMgr.add(self.update, "update")
        self.taskMgr.add(self.vr_manager.update, "vr_update")
    
    def start_vr_mode(self):
        """Запуск у VR режимі"""
        print("[VR] Запуск у VR режимі")
        
        # Приховуємо курсор
        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)
        
        # Інтро текст в VR
        self.create_vr_intro()
    
    def start_desktop_mode(self):
        """Запуск у десктоп режимі"""
        print("[DESKTOP] Запуск у десктоп режимі")
        
        # Інтро текст
        self.intro = OnscreenText(text="Welcome to Virtual Reality Simulation Life",
                                 pos=(0, 0.8), scale=0.07, fg=(1, 0.5, 0.8, 1))
        self.taskMgr.doMethodLater(3, self.remove_intro, "removeIntro")
        
        # Камера
        self.camera.setPos(0, -40, 20)
        self.camera.lookAt(0, 0, 0)
        
        # Управління
        self.accept("w", self.move_desktop, [0, 1, 0])
        self.accept("s", self.move_desktop, [0, -1, 0])
        self.accept("a", self.move_desktop, [-1, 0, 0])
        self.accept("d", self.move_desktop, [1, 0, 0])
    
    def create_vr_intro(self):
        """Створення VR інтро"""
        intro_root = render.attachNewNode("VRIntro")
        intro_root.setPos(self.camera.getPos() + Vec3(0, 5, 0))
        intro_root.lookAt(self.camera)
        
        intro_text = TextNode('intro')
        intro_text.setText("Welcome to\nVirtual Reality\nSimulation Life")
        intro_text.setFont(loader.loadFont("cmss12"))
        intro_node = intro_root.attachNewNode(intro_text)
        intro_node.setScale(0.5)
        intro_node.setPos(-2, 0, 0)
        
        self.taskMgr.doMethodLater(3, lambda t: intro_root.removeNode(), "remove_vr_intro")
    
    def create_world(self):
        """Створення світу"""
        # Підлога
        floor = loader.loadModel("models/box")
        floor.setScale(100, 100, 0.1)
        floor.setPos(0, 0, -0.5)
        floor.setColor(0.3, 0.3, 0.3, 1)
        floor.reparentTo(self.world)
        
        # Сітка на підлозі для орієнтації в VR
        grid = self.create_grid()
        grid.reparentTo(self.world)
        
        # Об'єкти
        for i in range(-5, 6, 2):
            for j in range(-5, 6, 2):
                obj = loader.loadModel("models/box")
                obj.setScale(0.5)
                obj.setPos(i, j, 0)
                obj.setColor(random.random(), random.random(), random.random(), 1)
                obj.reparentTo(self.world)
        
        # Освітлення
        self.setup_lighting()
    
    def create_grid(self):
        """Створення сітки для орієнтації"""
        grid_root = NodePath("Grid")
        
        # Лінії сітки
        for i in range(-10, 11, 1):
            line = loader.loadModel("models/box")
            line.setScale(0.05, 20, 0.01)
            line.setPos(i, 0, -0.4)
            line.setColor(0.5, 0.5, 0.5, 0.3)
            line.setTransparency(TransparencyAttrib.MAlpha)
            line.reparentTo(grid_root)
            
            line2 = loader.loadModel("models/box")
            line2.setScale(20, 0.05, 0.01)
            line2.setPos(0, i, -0.4)
            line2.setColor(0.5, 0.5, 0.5, 0.3)
            line2.setTransparency(TransparencyAttrib.MAlpha)
            line2.reparentTo(grid_root)
        
        return grid_root
    
    def setup_lighting(self):
        """Налаштування освітлення"""
        # Основне світло
        ambient_light = AmbientLight('ambient')
        ambient_light.setColor(Vec4(0.3, 0.3, 0.3, 1))
        ambient_light_node = render.attachNewNode(ambient_light)
        render.setLight(ambient_light_node)
        
        # Направлене світло
        directional_light = DirectionalLight('directional')
        directional_light.setColor(Vec4(0.8, 0.8, 0.8, 1))
        directional_light_node = render.attachNewNode(directional_light)
        directional_light_node.setHpr(45, -30, 0)
        render.setLight(directional_light_node)
        
        # Точкове світло для аніме-ефектів
        point_light = PointLight('point')
        point_light.setColor(Vec4(0.5, 0.5, 1, 1))
        point_light_node = render.attachNewNode(point_light)
        point_light_node.setPos(0, 0, 5)
        render.setLight(point_light_node)
    
    def move_vr(self, x, y):
        """Переміщення в VR"""
        if not self.vr_manager.vr_initialized:
            return
        
        # Переміщення в напрямку погляду
        direction = self.camera.getQuat().getForward()
        speed = 0.05
        
        move_vec = (direction * y * speed) + (direction * x * speed)
        self.vr_manager.vr_origin.setPos(self.vr_manager.vr_origin.getPos() + move_vec)
    
    def rotate_vr(self, x):
        """Поворот в VR"""
        if not self.vr_manager.vr_initialized:
            return
        
        # Snap turn
        snap_amount = self.config.get("vr_snap_turn", 45)
        if abs(x) > 0.7:
            self.vr_manager.vr_origin.setH(self.vr_manager.vr_origin.getH() + snap_amount * x)
    
    def move_desktop(self, dx, dy, dz=0):
        """Переміщення в десктоп режимі"""
        if not hasattr(self, 'avatar'):
            self.avatar = render.attachNewNode("Avatar")
        
        speed = 0.5
        new_pos = self.avatar.getPos() + Vec3(dx * speed, dy * speed, dz * speed)
        self.avatar.setPos(new_pos)
    
    def remove_intro(self, task):
        if hasattr(self, 'intro'):
            self.intro.destroy()
        return task.done
    
    def show_pause_menu(self):
        """Показ меню паузи"""
        if self.simulation_running:
            if self.vr_manager.vr_initialized:
                self.show_vr_pause_menu()
            else:
                self.show_desktop_pause_menu()
    
    def show_vr_pause_menu(self):
        """VR меню паузи"""
        pause_root = render.attachNewNode("PauseMenu")
        pause_root.setPos(self.camera.getPos() + Vec3(0, 3, 0))
        pause_root.lookAt(self.camera)
        
        # Текст
        pause_text = TextNode('pause')
        pause_text.setText("PAUSED")
        pause_text.setFont(loader.loadFont("cmss12"))
        pause_node = pause_root.attachNewNode(pause_text)
        pause_node.setScale(0.3)
        pause_node.setPos(-1, 0, 1)
        
        # Кнопка Resume
        resume_btn = loader.loadModel("models/box")
        resume_btn.setScale(2, 0.2, 0.5)
        resume_btn.setColor(0.3, 0.6, 1, 0.8)
        resume_btn.setPos(0, 0, 0)
        resume_btn.reparentTo(pause_root)
        
        resume_text = TextNode('resume')
        resume_text.setText("Resume")
        resume_node = pause_root.attachNewNode(resume_text)
        resume_node.setScale(0.2)
        resume_node.setPos(-0.6, 0.1, 0)
        
        # Закриття через 5 секунд
        self.taskMgr.doMethodLater(5, lambda t: pause_root.removeNode(), "close_pause_menu")
    
    def show_desktop_pause_menu(self):
        """Десктоп меню паузи"""
        pause_frame = DirectFrame(frameColor=(0, 0, 0, 0.8), frameSize=(-0.3, 0.3, -0.3, 0.3))
        DirectLabel(text="PAUSED", text_scale=0.1, pos=(0, 0, 0.1), parent=pause_frame)
        DirectButton(text="Resume", scale=0.05, pos=(0, 0, -0.1),
                    command=pause_frame.destroy, parent=pause_frame)
    
    def update(self, task):
        """Головний цикл оновлення"""
        if not self.vr_manager.vr_initialized and hasattr(self, 'avatar'):
            # Десктоп режим - камера слідкує за аватаром
            t = task.time
            self.camera.setZ(20 + math.sin(t) * 0.2)
            self.camera.lookAt(self.avatar)
        
        return task.cont

# ============================================
# RUN APP
# ============================================
if __name__ == "__main__":
    print("=" * 50)
    print("SAO VR Simulator - MyUp Edition")
    print("OPENXR VR READY")
    print("=" * 50)
    
    # Перевірка OpenXR
    if OPENXR_AVAILABLE:
        print("[OK] OpenXR доступний")
    else:
        print("[WARN] OpenXR не доступний, робота в десктоп режимі")
    
    app = SimulatorVR()
    app.run()
