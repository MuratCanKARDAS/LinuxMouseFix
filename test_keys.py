import sys
import time
sys.path.append("/run/media/mck/Yeni Birim/AntiGravity/mouse")
from evdev import UInput, ecodes
from actions import ActionExecutor

cap = {
    ecodes.EV_KEY: [
        ecodes.KEY_LEFTMETA, ecodes.KEY_LEFTALT, ecodes.KEY_LEFT, ecodes.KEY_RIGHT
    ]
}
ui = UInput(cap, name="Test-Virtual")
executor = ActionExecutor(ui)

time.sleep(1)
print("Sending moveRightDesktop...")
executor.execute("moveRightDesktop")
ui.syn()
time.sleep(0.5)
ui.close()
print("Done.")
