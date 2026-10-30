"""
ARC Raiders Sound Overlay - Spectral Flux Transient Engine (v3.5)
Uses Spectral Flux Onset Detection to mathematically separate Left, Right,
Front, and Rear sounds while completely rejecting background noise.
"""

import threading
import time
from collections import deque
import numpy as np
import pyaudiowpatch as pyaudio

class AudioEngine:
    def __init__(self, sample_rate=44100, chunk_size=1024):
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.running = False
        self.thread = None
        self.p = None
        self.stream = None
        self.selected_device_index = None

        # User Configurable
        self.gain = 3.0
        self.noise_threshold = 0.002
        self.hold_duration = 0.95
        self.stereo_boost = 1.4

        # Active sound threats list
        self.threats = []
        self.lock = threading.Lock()

        # Overall levels for meters
        self.level_l = 0.0
        self.level_r = 0.0
        self.decay_speed = 0.85

    def get_output_devices(self):
        p = pyaudio.PyAudio()
        devices = []
        try:
            for dev in p.get_loopback_device_info_generator():
                devices.append({
                    "index": dev["index"],
                    "name": dev["name"],
                    "channels": dev["maxInputChannels"],
                    "sample_rate": int(dev["defaultSampleRate"])
                })
        except Exception as e:
            print(f"Error enumerating devices: {e}")
        finally:
            p.terminate()
        return devices

    def get_default_loopback_device(self, p_inst=None):
        should_close = False
        if p_inst is None:
            p = pyaudio.PyAudio()
            should_close = True
        else:
            p = p_inst

        loopback_dev = None
        try:
            loopback_dev = p.get_default_wasapi_loopback()
        except Exception:
            try:
                for dev in p.get_loopback_device_info_generator():
                    loopback_dev = dev
                    break
            except Exception:
                pass
        finally:
            if should_close:
                p.terminate()
        return loopback_dev

    def start(self, device_index=None):
        if self.running:
            return
        self.selected_device_index = device_index
        self.running = True
        self.thread = threading.Thread(target=self._run_capture, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self._cleanup_stream()

    def _cleanup_stream(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

    def _register_threat(self, angle, kind, power, dist_label):
        now = time.time()
        # Merge if nearby threat of same kind exists
        for t in self.threats:
            if t["kind"] == kind and abs(t["angle"] - angle) < 26.0:
                t["angle"] = t["angle"] * 0.35 + angle * 0.65
                t["power"] = max(t["power"], power)
                t["timestamp"] = now
                t["distance"] = dist_label
                return

        self.threats.append({
            "angle": float(angle),
            "kind": kind,
            "power": float(power),
            "distance": dist_label,
            "timestamp": now
        })

    def _run_capture(self):
        while self.running:
            try:
                self.p = pyaudio.PyAudio()
                if self.selected_device_index is not None:
                    dev_info = self.p.get_device_info_by_index(self.selected_device_index)
                else:
                    dev_info = self.get_default_loopback_device(self.p)

                if not dev_info:
                    time.sleep(1.5)
                    continue

                channels = dev_info["maxInputChannels"]
                rate = int(dev_info["defaultSampleRate"])
                self.sample_rate = rate

                num_bins = self.chunk_size // 2 + 1
                freqs = np.fft.rfftfreq(self.chunk_size, 1.0 / rate)

                # Frequency Masks
                footstep_mask = (freqs >= 65) & (freqs <= 3600)
                combat_mask = (freqs >= 1200) & (freqs <= 7500)
                hf_pinna_mask = (freqs >= 4000) & (freqs <= 8500)
                lf_pinna_mask = (freqs >= 200) & (freqs <= 1200)

                self.stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=dev_info["index"],
                    frames_per_buffer=self.chunk_size
                )

                hann = np.hanning(self.chunk_size)
                prev_fft_l = np.zeros(num_bins, dtype=np.float32)
                prev_fft_r = np.zeros(num_bins, dtype=np.float32)
                flux_history = deque(maxlen=40)

                while self.running:
                    try:
                        raw_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                        if not raw_data:
                            continue

                        samples = np.frombuffer(raw_data, dtype=np.float32)
                        if len(samples) < self.chunk_size * channels:
                            continue

                        samples = samples.reshape(-1, channels)
                        now = time.time()

                        # Channel separation
                        if channels >= 8:
                            ch_l = samples[:, 0] + samples[:, 6] * 1.2 + samples[:, 4] * 0.8
                            ch_r = samples[:, 1] + samples[:, 7] * 1.2 + samples[:, 5] * 0.8
                            rear_energy = float(np.sqrt(np.mean((samples[:, 4] + samples[:, 5])**2)))
                        elif channels >= 6:
                            ch_l = samples[:, 0] + samples[:, 4] * 0.8
                            ch_r = samples[:, 1] + samples[:, 5] * 0.8
                            rear_energy = float(np.sqrt(np.mean((samples[:, 4] + samples[:, 5])**2)))
                        else:
                            ch_l = samples[:, 0]
                            ch_r = samples[:, 1]
                            rear_energy = 0.0

                        rms_l = float(np.sqrt(np.mean(ch_l**2)))
                        rms_r = float(np.sqrt(np.mean(ch_r**2)))
                        tot_rms = (rms_l + rms_r) / 2.0

                        # Smooth levels for GUI meters
                        comp_l = min(1.0, float(np.sqrt(rms_l) * self.gain))
                        comp_r = min(1.0, float(np.sqrt(rms_r) * self.gain))
                        self.level_l = max(comp_l, self.level_l * self.decay_speed)
                        self.level_r = max(comp_r, self.level_r * self.decay_speed)

                        # FFT
                        fft_l = np.abs(np.fft.rfft(ch_l * hann))
                        fft_r = np.abs(np.fft.rfft(ch_r * hann))

                        # SPECTRAL FLUX: Isolates NEW attack energy, canceling background
                        flux_l = float(np.sum(np.maximum(0.0, fft_l - prev_fft_l)))
                        flux_r = float(np.sum(np.maximum(0.0, fft_r - prev_fft_r)))
                        prev_fft_l = fft_l
                        prev_fft_r = fft_r

                        tot_flux = flux_l + flux_r

                        # Adaptive flux threshold
                        if len(flux_history) >= 20:
                            med_f = np.median(flux_history)
                            std_f = np.std(flux_history)
                            dynamic_thresh = max(14.0, med_f + 2.2 * std_f)
                        else:
                            dynamic_thresh = 18.0

                        flux_history.append(tot_flux)

                        # Check if a REAL sound transient happened
                        if tot_flux > dynamic_thresh and tot_rms > self.noise_threshold:
                            # 1. Precise Stereo Panning from Spectral Flux
                            diff_flux = flux_r - flux_l
                            denom_flux = flux_l + flux_r + 1e-6
                            panning = diff_flux / denom_flux

                            # Curved expansion with boost
                            curved_p = np.sign(panning) * (abs(panning) ** 0.38) * self.stereo_boost
                            curved_p = float(np.clip(curved_p, -1.0, 1.0))
                            angle_deg = curved_p * 90.0 # -90° (Left) to +90° (Right)

                            # 2. Front vs Behind Classification
                            # Pinna Filter: High-frequency ratio of the transient
                            combined_fft = (fft_l + fft_r) / 2.0
                            hf_pinna = float(np.sum(combined_fft[hf_pinna_mask]))
                            lf_pinna = float(np.sum(combined_fft[lf_pinna_mask]))
                            pinna_ratio = hf_pinna / (lf_pinna + 1e-5)

                            is_behind = False
                            # Confirmation via 7.1 rear channels OR pinna acoustic shadow
                            if channels >= 6 and rear_energy > tot_rms * 1.30 and rear_energy > 0.010:
                                is_behind = True
                            elif pinna_ratio < 0.18 and lf_pinna > 10.0:
                                # High frequencies muffled by rear head/ear shadow
                                is_behind = True

                            if is_behind:
                                # Map to rear quadrant
                                angle_deg = 180.0 - angle_deg if angle_deg >= 0 else -180.0 - angle_deg

                            # 3. Sound Kind Classification
                            combat_e = float(np.mean(combined_fft[combat_mask]))
                            step_e = float(np.mean(combined_fft[footstep_mask]))

                            if combat_e > step_e * 1.25 and combat_e > 1.2:
                                kind = "gunshot"
                                pwr = min(1.0, combat_e * 0.25)
                            elif step_e > 0.8:
                                kind = "footstep"
                                pwr = min(1.0, step_e * 0.35)
                            else:
                                kind = "general"
                                pwr = min(1.0, tot_flux / 50.0)

                            # 4. Distance Estimation
                            if pwr > 0.55 or tot_rms > 0.07:
                                dist_lbl = "close"
                            elif pwr > 0.20 or tot_rms > 0.02:
                                dist_lbl = "medium"
                            else:
                                dist_lbl = "far"

                            with self.lock:
                                self._register_threat(angle_deg, kind, pwr, dist_lbl)

                    except Exception:
                        time.sleep(0.01)

            except Exception as e:
                print(f"Audio Engine capture error: {e}")
                time.sleep(1.0)
            finally:
                self._cleanup_stream()

    def get_state(self):
        now = time.time()
        with self.lock:
            active_threats = []
            for t in self.threats:
                age = now - t["timestamp"]
                if age < self.hold_duration:
                    solid_window = self.hold_duration * 0.45
                    if age < solid_window:
                        opac = 1.0
                    else:
                        opac = 1.0 - (age - solid_window) / (self.hold_duration - solid_window)
                    
                    t_item = dict(t)
                    t_item["opacity"] = max(0.0, min(1.0, float(opac)))
                    active_threats.append(t_item)

            self.threats = [t for t in self.threats if (now - t["timestamp"]) < self.hold_duration]

            return {
                "threats": active_threats,
                "level_l": self.level_l,
                "level_r": self.level_r
            }
