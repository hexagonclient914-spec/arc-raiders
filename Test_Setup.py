"""
ARC Raiders - Audio & Headset Diagnostic Check
Tests Logitech G PRO X Stereo Sound, Frequency Response, and Direction Panning.
"""

import time
import numpy as np
import sounddevice as sd

def run_audio_check():
    print("=" * 55)
    print("   ARC RAIDERS - AUDIO SETUP & DIAGNOSTIC TEST")
    print("=" * 55)
    
    sr = 48000
    try:
        dev = sd.query_devices(sd.default.device[1])
        print(f"[OK] Aktives Ausgabegeraet: {dev['name']}")
        print(f"[OK] Standard Samplerate: {int(dev['default_samplerate'])} Hz")
    except Exception as e:
        print(f"[WARN] Audio-Abfrage: {e}")

    print("\n[1/3] Teste LINKES Ohr (Schritte / Trittschall)...")
    dur = 0.4
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    env = np.exp(-8 * t)
    sig_left = (0.4 * np.sin(2 * np.pi * 180 * t) + 0.3 * np.sin(2 * np.pi * 2200 * t)) * env
    stereo_l = np.column_stack((sig_left, np.zeros_like(sig_left)))
    sd.play(stereo_l.astype(np.float32), sr)
    sd.wait()
    time.sleep(0.3)

    print("[2/3] Teste RECHTES Ohr (Schuss / Treffer)...")
    noise = np.random.uniform(-0.25, 0.25, len(t))
    sig_right = (0.35 * np.sin(2 * np.pi * 2600 * t) + noise * 0.35) * env
    stereo_r = np.column_stack((np.zeros_like(sig_right), sig_right))
    sd.play(stereo_r.astype(np.float32), sr)
    sd.wait()
    time.sleep(0.3)

    print("[3/3] Teste ZENTRUM (Gleichmaessig vorne)...")
    sig_c = 0.3 * np.sin(2 * np.pi * 1200 * t) * env
    stereo_c = np.column_stack((sig_c, sig_c))
    sd.play(stereo_c.astype(np.float32), sr)
    sd.wait()

    print("\n" + "=" * 55)
    print("DIAGNOSE ABGESCHLOSSEN!")
    print("Wenn du die Sounds sauber links, rechts und mittig gehoert hast,")
    print("ist dein Headset perfekt fuer ARC Raiders eingestellt!")
    print("=" * 55)

if __name__ == "__main__":
    run_audio_check()
