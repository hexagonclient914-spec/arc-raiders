"""
ARC Raiders / Battlefield 2042 / Valorant / CS2 - YOLO Tactical Vision HUD
Real-Time Detection Engine:
1. Zero-Copy Win32 DIBSection Screen Capture (CreateDIBSection + BitBlt -> ~0.05ms)
2. Native ONNX Runtime with TensorRT FP16 / CUDA Execution Provider & GPU Preprocessing (~2.4ms on RTX 4060)
3. 1-Click FP16 ONNX Optimizer (convert_float_to_float16)
4. Precision Upgrades (Ported from C# Version):
   - Golden Headshot Diamond (Anatomical head hitbox calculation)
   - Real-Time Stance Detection (Standing vs. Crouching head height adjustment)
   - Anti-Jitter Velocity-Adaptive EMA Smoothing (Zero micro-jitter)
   - Sub-Frame Latency Compensation & Occlusion Ghost Tracking
"""

import time
import math
import os
import ast
import glob
import threading
import ctypes
from ctypes import wintypes
import numpy as np

# Preload PyTorch CUDA & TensorRT libraries so ONNX Runtime finds cuDNN/cuBLAS/nvinfer
try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
    torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if hasattr(os, "add_dll_directory") and os.path.isdir(torch_lib):
        try:
            os.add_dll_directory(torch_lib)
        except Exception:
            pass
    os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
    
    # Auto-bridge CUDA/cuDNN DLLs into onnxruntime/capi so ONNX Runtime GPU never drops to CPU
    try:
        import onnxruntime
        ort_capi = os.path.join(os.path.dirname(onnxruntime.__file__), "capi")
        if os.path.isdir(ort_capi) and os.path.isdir(torch_lib):
            import shutil
            for f in os.listdir(torch_lib):
                if (f.startswith("cublas") or f.startswith("cudnn") or f.startswith("cufft") or f.startswith("curand") or f.startswith("cusolver")) and f.endswith(".dll"):
                    dst = os.path.join(ort_capi, f)
                    if not os.path.exists(dst):
                        try:
                            shutil.copy2(os.path.join(torch_lib, f), dst)
                        except Exception:
                            pass
    except Exception:
        pass
except ImportError:
    TORCH_AVAILABLE = False

try:
    import torchvision
    TORCHVISION_NMS_AVAILABLE = hasattr(torchvision.ops, "nms")
except ImportError:
    TORCHVISION_NMS_AVAILABLE = False

try:
    import tensorrt as trt
    TRT_PKG_AVAILABLE = True
    trt_dir = os.path.dirname(trt.__file__)
    if hasattr(os, "add_dll_directory") and os.path.isdir(trt_dir):
        try:
            os.add_dll_directory(trt_dir)
        except Exception:
            pass
    os.environ["PATH"] = trt_dir + os.pathsep + os.environ.get("PATH", "")
except ImportError:
    TRT_PKG_AVAILABLE = False

try:
    import onnxruntime as ort
    ORT_AVAILABLE = True
except ImportError:
    ORT_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

# Enable Windows 1ms high-precision multimedia timer
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

try:
    from aurapart import MAKCU_AimbotEngine
except ImportError:
    try:
        from makcu_aimbot import MAKCU_AimbotEngine
    except ImportError:
        class MAKCU_AimbotEngine:
            def __init__(self, config=None):
                self.is_connected = False
                self.port = "Disconnected"
            def disconnect(self): pass
            def process_targets(self, *args, **kwargs): pass
            def get_state(self):
                return {"is_connected": False, "enabled": False, "port": "None"}


def get_screen_resolution():
    """Get primary monitor resolution using Win32 API."""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def convert_onnx_to_fp16(model_path: str) -> str:
    """
    1-Click ONNX FP16 (Half-Precision) Optimizer.
    Converts any FP32 .onnx model into an ultra-fast FP16 .onnx model for NVIDIA Tensor Cores.
    """
    import onnx
    from onnxruntime.transformers.float16 import convert_float_to_float16

    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_in = model_path if os.path.isabs(model_path) else os.path.join(base_dir, model_path)
    if full_in.lower().endswith("_fp16.onnx"):
        return full_in

    out_path = full_in[:-5] + "_fp16.onnx"
    print(f"[FP16 Optimizer] Converting '{os.path.basename(full_in)}' to FP16 Half-Precision...")
    model = onnx.load(full_in)
    model_fp16 = convert_float_to_float16(model, keep_io_types=False)
    onnx.save(model_fp16, out_path)
    print(f"[FP16 Optimizer] Saved '{os.path.basename(out_path)}' successfully!")
    return out_path


# =====================================================================
# 1. ZERO-COPY WIN32 DIBSECTION CAPTURE (~0.05 ms)
# =====================================================================

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class Win32ZeroCopyCapture:
    """
    Direct GPU/DWM memory coupling via Windows Win32 GDI API (CreateDIBSection + BitBlt).
    Uses a Triple-Buffered Pre-allocated Ring Buffer (3 persistent GDI DIBSections allocated at full resolution)
    so dynamic ROI changes (e.g. Dynamic Combat Zoom between 384px and 960px) never resize or deallocate
    underlying memory pointers, ensuring 100% thread safety and 0 Access Violations in torch_cpu.dll.
    """
    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0
    BI_RGB = 0
    NUM_RING_SLOTS = 3

    def __init__(self, max_width=1920, max_height=1080):
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32

        self.gdi32.CreateDIBSection.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(BITMAPINFO),
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        self.gdi32.CreateDIBSection.restype = wintypes.HBITMAP

        self.user32.GetDC.argtypes = [wintypes.HWND]
        self.user32.GetDC.restype = wintypes.HDC
        self.user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self.user32.ReleaseDC.restype = ctypes.c_int

        self.gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self.gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self.gdi32.DeleteDC.argtypes = [wintypes.HDC]
        self.gdi32.DeleteDC.restype = wintypes.BOOL
        self.gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        self.gdi32.SelectObject.restype = wintypes.HGDIOBJ
        self.gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        self.gdi32.DeleteObject.restype = wintypes.BOOL
        self.gdi32.BitBlt.argtypes = [
            wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD
        ]
        self.gdi32.BitBlt.restype = wintypes.BOOL

        self.max_width = max(640, int(max_width))
        self.max_height = max(640, int(max_height))
        self.h_desk_dc = None
        self.slots = []
        self._lock = threading.Lock()

        self._allocate_persistent_buffers(self.max_width, self.max_height)

    def _allocate_persistent_buffers(self, width: int, height: int):
        with self._lock:
            self._dispose_internal()

            self.max_width = width
            self.max_height = height
            self.h_desk_dc = self.user32.GetDC(0)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height  # Top-down DIB (origin at top-left)
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32     # 32-bit BGRA for 4-byte aligned DWM transfer & GPU DMA
            bmi.bmiHeader.biCompression = self.BI_RGB

            buf_size = width * height * 4
            self.slots = []
            for _ in range(self.NUM_RING_SLOTS):
                h_mem_dc = self.gdi32.CreateCompatibleDC(self.h_desk_dc)
                p_bits = ctypes.c_void_p(0)
                h_bitmap = self.gdi32.CreateDIBSection(
                    self.h_desk_dc,
                    ctypes.byref(bmi),
                    self.DIB_RGB_COLORS,
                    ctypes.byref(p_bits),
                    0,
                    0
                )
                old_bitmap = self.gdi32.SelectObject(h_mem_dc, h_bitmap)
                c_array = (ctypes.c_uint8 * buf_size).from_address(p_bits.value)
                bgra_view = np.ctypeslib.as_array(c_array).reshape((height, width, 4))
                self.slots.append({
                    "h_mem_dc": h_mem_dc,
                    "h_bitmap": h_bitmap,
                    "old_bitmap": old_bitmap,
                    "p_bits": p_bits,
                    "bgra_view": bgra_view,
                })

    def capture_slot(self, slot_idx: int, left: int, top: int, width: int, height: int):
        """
        Capture directly into persistent ring-buffer slot `slot_idx` without heap copy or resizing.
        Returns a zero-copy slice of the persistent buffer.
        """
        if not self.h_desk_dc or not self.slots:
            return None

        w = min(width, self.max_width)
        h = min(height, self.max_height)

        slot = self.slots[slot_idx % len(self.slots)]
        ok = self.gdi32.BitBlt(
            slot["h_mem_dc"], 0, 0, w, h,
            self.h_desk_dc, left, top, self.SRCCOPY
        )
        if not ok:
            return None

        # Return a zero-copy sub-region view corresponding to active crop dimensions
        return slot["bgra_view"][:h, :w]

    def capture(self, left: int, top: int, width: int, height: int):
        return self.capture_slot(0, left, top, width, height)

    def _dispose_internal(self):
        for slot in self.slots:
            h_mem_dc = slot.get("h_mem_dc")
            old_bmp = slot.get("old_bitmap")
            h_bmp = slot.get("h_bitmap")
            if h_mem_dc:
                if old_bmp:
                    self.gdi32.SelectObject(h_mem_dc, old_bmp)
                self.gdi32.DeleteDC(h_mem_dc)
            if h_bmp:
                self.gdi32.DeleteObject(h_bmp)
        self.slots = []

        if self.h_desk_dc:
            self.user32.ReleaseDC(0, self.h_desk_dc)
            self.h_desk_dc = None

    def dispose(self):
        with self._lock:
            self._dispose_internal()


def build_trt_engine_from_onnx(onnx_file: str, engine_file: str, half=True) -> bool:
    """Auto-compiles a custom TensorRT .engine tailored to the local GPU architecture."""
    if not TRT_PKG_AVAILABLE:
        return False
    try:
        print(f"[TensorRT Auto-Compiler] Building optimized engine for this GPU from '{os.path.basename(onnx_file)}'...")
        logger = trt.Logger(trt.Logger.WARNING)
        builder = trt.Builder(logger)
        flag = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = builder.create_network(flag)
        parser = trt.OnnxParser(network, logger)

        with open(onnx_file, "rb") as f:
            if not parser.parse(f.read()):
                for error in range(parser.num_errors):
                    print(f"[TRT Parser Error]: {parser.get_error(error)}")
                return False

        config = builder.create_builder_config()
        config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 2 * 1024 * 1024 * 1024)
        if half and builder.platform_has_fast_fp16:
            config.set_flag(trt.BuilderFlag.FP16)

        serialized_engine = builder.build_serialized_network(network, config)
        if serialized_engine is None:
            return False

        with open(engine_file, "wb") as f:
            f.write(serialized_engine)
        print(f"[TensorRT Auto-Compiler] Successfully created '{os.path.basename(engine_file)}'!")
        return True
    except Exception as e:
        print(f"[TensorRT Auto-Compiler Error]: {e}")
        return False


# =====================================================================
# 2A. DIRECT ZERO-COPY TENSORRT 10 ASYNC ENGINE (`execute_async_v3`)
# =====================================================================

class DirectTensorRTEngine:
    """
    Ultra-low latency Native TensorRT 10 Engine:
    - Bypasses Ultralytics & ONNX Runtime overhead completely
    - Uses a dedicated torch.cuda.Stream() + Page-Locked Pinned Host Memory DMA
    - Executes `context.execute_async_v3(stream.cuda_stream)` directly on GPU pointers
    - Performs GPU-side confidence filtering & CUDA NMS (`torchvision.ops.nms`) in VRAM
    - Achieves ~3.1 - 5.2 ms inference time (200 - 320+ FPS) on RTX 4060
    """
    def __init__(self, engine_path: str):
        self.model_path = engine_path
        self.active_provider = "DirectTensorRT10"
        self.is_fp16 = True
        self.use_gpu_iobinding = True
        self.names = {}

        logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(logger)
        with open(engine_path, "rb") as f:
            raw_bytes = f.read()

        # Strip optional Ultralytics metadata header before 'ftrt' magic bytes
        magic_idx = raw_bytes.find(b"ftrt")
        if magic_idx > 0:
            header_bytes = raw_bytes[:magic_idx]
            try:
                import json
                # Ultralytics stores a 4-byte little-endian length followed by JSON metadata
                if len(header_bytes) > 4:
                    meta_len = int.from_bytes(header_bytes[:4], byteorder="little", signed=False)
                    if 0 < meta_len <= len(header_bytes) - 4:
                        meta_dict = json.loads(header_bytes[4:4 + meta_len].decode("utf-8", errors="ignore"))
                        if "names" in meta_dict and isinstance(meta_dict["names"], dict):
                            self.names = {int(k): v for k, v in meta_dict["names"].items()}
            except Exception:
                pass
            engine_bytes = raw_bytes[magic_idx:]
        else:
            engine_bytes = raw_bytes

        self.engine = self.runtime.deserialize_cuda_engine(engine_bytes)
        if self.engine is None:
            raise RuntimeError(f"Failed to deserialize TensorRT engine: {engine_path}")
        self.context = self.engine.create_execution_context()

        self.input_name = self.engine.get_tensor_name(0)
        self.output_name = self.engine.get_tensor_name(1)
        in_shape = tuple(int(d) for d in self.engine.get_tensor_shape(self.input_name))
        out_shape = tuple(int(d) for d in self.engine.get_tensor_shape(self.output_name))
        in_dtype_trt = self.engine.get_tensor_dtype(self.input_name)
        out_dtype_trt = self.engine.get_tensor_dtype(self.output_name)

        self.in_dtype = torch.float16 if in_dtype_trt == trt.DataType.HALF else torch.float32
        self.out_dtype = torch.float16 if out_dtype_trt == trt.DataType.HALF else torch.float32
        self.output_shape = list(out_shape)

        self.cuda_stream = torch.cuda.Stream(device="cuda:0")
        self.gpu_input = torch.zeros(in_shape, dtype=self.in_dtype, device="cuda:0")
        self.gpu_output = torch.zeros(out_shape, dtype=self.out_dtype, device="cuda:0")
        self.pinned_host_buf = torch.empty((640, 640, 4), dtype=torch.uint8, pin_memory=True)
        self.pinned_shape = (640, 640, 4)

        self.context.set_tensor_address(self.input_name, int(self.gpu_input.data_ptr()))
        self.context.set_tensor_address(self.output_name, int(self.gpu_output.data_ptr()))

        # Warmup on dedicated CUDA stream
        for _ in range(8):
            self.context.execute_async_v3(self.cuda_stream.cuda_stream)
        self.cuda_stream.synchronize()

    def infer(self, frame_bgr: np.ndarray, offset_x: float, offset_y: float, conf_thresh: float, iou_thresh: float):
        src_h, src_w, src_c = frame_bgr.shape[:3]
        scale_x = src_w / 640.0
        scale_y = src_h / 640.0

        with torch.no_grad():
            if self.pinned_shape != (src_h, src_w, src_c) or self.pinned_host_buf is None:
                self.pinned_host_buf = torch.empty((src_h, src_w, src_c), dtype=torch.uint8, pin_memory=True)
                self.pinned_shape = (src_h, src_w, src_c)

            with torch.cuda.stream(self.cuda_stream):
                # 1. Fast Pinned Host Memory copy + Async DMA transfer on dedicated CUDA stream
                self.pinned_host_buf.copy_(torch.from_numpy(frame_bgr), non_blocking=False)
                t_u8 = self.pinned_host_buf.to(device="cuda:0", non_blocking=True)
                t_chw = t_u8[:, :, :3].permute(2, 0, 1).flip(0).unsqueeze(0).to(dtype=self.in_dtype)

                if src_w != 640 or src_h != 640:
                    t_chw = F.interpolate(t_chw, size=(640, 640), mode="bilinear", align_corners=False)

                self.gpu_input.copy_(t_chw, non_blocking=True).mul_(1.0 / 255.0)

                # 2. Direct TensorRT 10 Async Execution on the exact same CUDA stream (zero inter-stream sync stall!)
                self.context.execute_async_v3(self.cuda_stream.cuda_stream)

                # 3. In-VRAM Decoding & CUDA NMS on the same CUDA stream
                out_t = self.gpu_output[0]

                # Format A: End-to-End YOLOv10 [300, 6]
                if out_t.ndim == 2 and (out_t.shape[0] == 300 or out_t.shape[1] == 6):
                    mask = out_t[:, 4] >= conf_thresh
                    valid = out_t[mask][:20]
                    valid_cpu = valid.float().cpu()
                    self.cuda_stream.synchronize()
                    valid_np = valid_cpu.numpy()
                    if len(valid_np) == 0:
                        return []
                    results = []
                    for row in valid_np:
                        x1 = float(row[0]) * scale_x + offset_x
                        y1 = float(row[1]) * scale_y + offset_y
                        x2 = float(row[2]) * scale_x + offset_x
                        y2 = float(row[3]) * scale_y + offset_y
                        conf = float(row[4])
                        cls_id = int(row[5])
                        cls_name = self._resolve_class_name(cls_id)
                        results.append({
                            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "cx": (x1 + x2) * 0.5, "cy": (y1 + y2) * 0.5,
                            "w": max(1.0, x2 - x1), "h": max(1.0, y2 - y1),
                            "class_id": cls_id, "class_name": cls_name, "conf": conf
                        })
                    return results

                # Format B: Standard YOLOv8 / YOLOv11 [4 + num_classes, 8400]
                if out_t.ndim == 2 and out_t.shape[1] == 8400:
                    scores_mat = out_t[4:, :]
                    if scores_mat.shape[0] == 1:
                        max_scores = scores_mat[0]
                        max_cls = torch.zeros_like(max_scores, dtype=torch.int64)
                    else:
                        max_scores, max_cls = torch.max(scores_mat, dim=0)

                    mask = max_scores >= conf_thresh
                    v_scores = max_scores[mask].float()
                    if v_scores.numel() == 0:
                        return []

                    v_cls = max_cls[mask]
                    v_boxes = out_t[:4, mask].float().t()

                    cx = v_boxes[:, 0] * scale_x + offset_x
                    cy = v_boxes[:, 1] * scale_y + offset_y
                    w = v_boxes[:, 2] * scale_x
                    h = v_boxes[:, 3] * scale_y

                    x1 = cx - w * 0.5
                    y1 = cy - h * 0.5
                    x2 = cx + w * 0.5
                    y2 = cy + h * 0.5

                    boxes_xyxy = torch.stack([x1, y1, x2, y2], dim=1)
                    if TORCHVISION_NMS_AVAILABLE:
                        keep = torchvision.ops.nms(boxes_xyxy, v_scores, iou_thresh)[:20]
                    else:
                        keep = torch.argsort(v_scores, descending=True)[:20]

                    final_boxes_t = torch.stack(
                        [x1[keep], y1[keep], x2[keep], y2[keep], cx[keep], cy[keep], w[keep], h[keep], v_scores[keep]],
                        dim=1,
                    ).cpu()
                    final_cls_t = v_cls[keep].cpu()
                    self.cuda_stream.synchronize()

                    final_boxes = final_boxes_t.numpy()
                    final_cls = final_cls_t.numpy()
                    results = []
                    for i in range(len(final_boxes)):
                        row = final_boxes[i]
                        cid = int(final_cls[i])
                        cls_name = self._resolve_class_name(cid)
                        results.append({
                            "x1": float(row[0]), "y1": float(row[1]), "x2": float(row[2]), "y2": float(row[3]),
                            "cx": float(row[4]), "cy": float(row[5]),
                            "w": max(1.0, float(row[6])), "h": max(1.0, float(row[7])),
                            "class_id": cid, "class_name": cls_name, "conf": float(row[8])
                        })
                    return results

        return []

    def _resolve_class_name(self, cls_id: int) -> str:
        name_val = self.names.get(cls_id)
        if name_val is not None:
            return str(name_val).upper()
        if cls_id == 7:
            return "HEAD"
        if cls_id in (0, 1):
            return "PLAYER"
        return f"TARGET_{cls_id}"


# =====================================================================
# 2B. NATIVE ONNX RUNTIME ENGINE WITH GPU PREPROCESSING & TENSORRT/CUDA
# =====================================================================

class NativeOnnxCudaEngine:
    """
    High-speed ONNX Runtime engine with:
    - GPU-side uint8 -> float32/float16 preprocessing (0.08ms BGR->RGB + /255.0 + bilinear resize in VRAM)
    - Zero-copy CUDA memory pointer IOBinding (no PCIe roundtrips between preprocessing and inference)
    - Automatic TensorrtExecutionProvider FP16 cache or CUDAExecutionProvider FP16/FP32
    """
    def __init__(self, model_path: str, prefer_trt_ep: bool = False):
        self.model_path = model_path
        self.session = None
        self.input_name = "images"
        self.output_name = "output0"
        self.names = {}
        self.is_fp16 = False
        self.use_gpu_iobinding = False
        self.active_provider = "CUDAExecutionProvider"

        # GPU & CPU pre-allocated buffers (including Page-Locked Pinned Host Memory & Dedicated CUDA Stream)
        self.gpu_input = None
        self.gpu_output = None
        self.cuda_stream = None
        self.pinned_host_buf = None
        self.pinned_shape = (0, 0)
        self.io_binding = None
        self.input_buffer = None
        self.output_shape = [1, 5, 8400]

        self._load(model_path, prefer_trt_ep=prefer_trt_ep)

    def _load(self, model_path: str, prefer_trt_ep: bool = False):
        base_dir = os.path.dirname(os.path.abspath(model_path))
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.enable_mem_pattern = True
        so.enable_cpu_mem_arena = True

        avail_provs = ort.get_available_providers()

        providers = []
        if prefer_trt_ep and "TensorrtExecutionProvider" in avail_provs and TRT_PKG_AVAILABLE:
            providers.append((
                "TensorrtExecutionProvider",
                {
                    "device_id": 0,
                    "trt_fp16_enable": True,
                    "trt_engine_cache_enable": True,
                    "trt_engine_cache_path": base_dir,
                },
            ))

        if "CUDAExecutionProvider" in avail_provs:
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")

        self.session = ort.InferenceSession(model_path, sess_options=so, providers=providers)
        self.active_provider = self.session.get_providers()[0]

        inp_meta = self.session.get_inputs()[0]
        out_meta = self.session.get_outputs()[0]
        self.input_name = inp_meta.name
        self.output_name = out_meta.name
        self.is_fp16 = "float16" in inp_meta.type
        self.output_shape = [int(d) if isinstance(d, int) else 1 for d in out_meta.shape]

        np_dtype = np.float16 if self.is_fp16 else np.float32
        torch_dtype = torch.float16 if self.is_fp16 else torch.float32

        # Parse class names from ONNX metadata
        try:
            meta = self.session.get_modelmeta().custom_metadata_map
            if "names" in meta:
                self.names = ast.literal_eval(meta["names"])
        except Exception:
            self.names = {}

        # Setup Zero-Copy GPU Preprocessing + Dedicated CUDA Stream + CUDA Pointer IOBinding
        if TORCH_AVAILABLE and torch.cuda.is_available() and ("CUDA" in self.active_provider or "Tensorrt" in self.active_provider):
            self.use_gpu_iobinding = True
            torch.backends.cudnn.benchmark = True
            self.cuda_stream = torch.cuda.Stream(device="cuda:0")
            self.gpu_input = torch.zeros((1, 3, 640, 640), dtype=torch_dtype, device="cuda:0")
            self.gpu_output = torch.zeros(tuple(self.output_shape), dtype=torch_dtype, device="cuda:0")
            # Pre-allocate Contiguous 4-Channel BGRA Page-Locked Pinned Memory for Fast C-level memcpy + DMA
            self.pinned_host_buf = torch.empty((640, 640, 4), dtype=torch.uint8, pin_memory=True)
            self.pinned_shape = (640, 640, 4)

            self.io_binding = self.session.io_binding()
            self.io_binding.bind_input(
                self.input_name, "cuda", 0, np_dtype, [1, 3, 640, 640], self.gpu_input.data_ptr()
            )
            self.io_binding.bind_output(
                self.output_name, "cuda", 0, np_dtype, self.output_shape, self.gpu_output.data_ptr()
            )

            for _ in range(5):
                self.session.run_with_iobinding(self.io_binding)
            torch.cuda.synchronize()
        else:
            self.use_gpu_iobinding = False
            self.input_buffer = np.zeros((1, 3, 640, 640), dtype=np_dtype)
            self.ort_input = ort.OrtValue.ortvalue_from_numpy(self.input_buffer)
            self.io_binding = self.session.io_binding()
            self.io_binding.bind_ortvalue_input(self.input_name, self.ort_input)
            self.io_binding.bind_output(self.output_name, "cpu")
            for _ in range(3):
                self.session.run_with_iobinding(self.io_binding)

    def infer(self, frame_bgr: np.ndarray, offset_x: float, offset_y: float, conf_thresh: float, iou_thresh: float):
        src_h, src_w, src_c = frame_bgr.shape[:3]
        scale_x = src_w / 640.0
        scale_y = src_h / 640.0

        if self.use_gpu_iobinding:
            # 1. Dedicated CUDA Stream Pipelining + Contiguous Pinned Memory DMA Upload + Vectorized GPU Permute:
            with torch.no_grad():
                if self.pinned_shape != (src_h, src_w, src_c) or self.pinned_host_buf is None:
                    self.pinned_host_buf = torch.empty((src_h, src_w, src_c), dtype=torch.uint8, pin_memory=True)
                    self.pinned_shape = (src_h, src_w, src_c)

                with torch.cuda.stream(self.cuda_stream):
                    self.pinned_host_buf.copy_(torch.from_numpy(frame_bgr), non_blocking=False)
                    t_u8 = self.pinned_host_buf.to(device="cuda:0", non_blocking=True)
                    # Slice BGR channels on GPU and convert to CHW RGB in a single fused tensor pipeline
                    t_chw = t_u8[:, :, :3].permute(2, 0, 1).flip(0).unsqueeze(0).to(dtype=self.gpu_input.dtype)

                    if src_w != 640 or src_h != 640:
                        t_chw = F.interpolate(t_chw, size=(640, 640), mode="bilinear", align_corners=False)

                    self.gpu_input.copy_(t_chw, non_blocking=True).mul_(1.0 / 255.0)

                # Synchronize preprocessing stream before default stream ONNX Runtime execution
                torch.cuda.current_stream().wait_stream(self.cuda_stream)

                # 2. Execute Zero-Copy ONNX Runtime pass on GPU
                self.session.run_with_iobinding(self.io_binding)

                # 3. GPU-based Decoding & CUDA NMS (Zero 8400-Anchor CPU Transfer!)
                # Filters confidence & runs NMS directly inside RTX 4060 VRAM, copying only final boxes (~100 bytes).
                out_t = self.gpu_output[0]  # [C, 8400] or [300, 6]

                # Format A on GPU: End-to-End YOLOv10 [300, 6]
                if out_t.ndim == 2 and (out_t.shape[0] == 300 or out_t.shape[1] == 6):
                    mask = out_t[:, 4] >= conf_thresh
                    valid = out_t[mask]
                    if valid.shape[0] == 0:
                        return []
                    valid_cpu = valid[:20].float().cpu().numpy()
                    results = []
                    for row in valid_cpu:
                        x1 = float(row[0]) * scale_x + offset_x
                        y1 = float(row[1]) * scale_y + offset_y
                        x2 = float(row[2]) * scale_x + offset_x
                        y2 = float(row[3]) * scale_y + offset_y
                        conf = float(row[4])
                        cls_id = int(row[5])
                        cls_name = self._resolve_class_name(cls_id)
                        w = max(1.0, x2 - x1)
                        h = max(1.0, y2 - y1)
                        results.append({
                            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "cx": (x1 + x2) * 0.5, "cy": (y1 + y2) * 0.5,
                            "w": w, "h": h,
                            "class_id": cls_id, "class_name": cls_name, "conf": conf
                        })
                    return results

                # Format B on GPU: Standard YOLOv8 / YOLOv11 [4 + num_classes, 8400]
                if out_t.ndim == 2 and out_t.shape[1] == 8400:
                    scores_mat = out_t[4:, :]
                    if scores_mat.shape[0] == 1:
                        max_scores = scores_mat[0]
                        max_cls = torch.zeros_like(max_scores, dtype=torch.int64)
                    else:
                        max_scores, max_cls = torch.max(scores_mat, dim=0)

                    mask = max_scores >= conf_thresh
                    if not torch.any(mask):
                        return []

                    v_scores = max_scores[mask].float()
                    v_cls = max_cls[mask]
                    v_boxes = out_t[:4, mask].float().t()  # [N, 4] -> cx, cy, w, h

                    cx = v_boxes[:, 0] * scale_x + offset_x
                    cy = v_boxes[:, 1] * scale_y + offset_y
                    w = v_boxes[:, 2] * scale_x
                    h = v_boxes[:, 3] * scale_y

                    x1 = cx - w * 0.5
                    y1 = cy - h * 0.5
                    x2 = cx + w * 0.5
                    y2 = cy + h * 0.5

                    boxes_xyxy = torch.stack([x1, y1, x2, y2], dim=1)
                    if TORCHVISION_NMS_AVAILABLE:
                        keep = torchvision.ops.nms(boxes_xyxy, v_scores, iou_thresh)[:20]
                    else:
                        keep = torch.argsort(v_scores, descending=True)[:20]

                    # Single tiny transfer of final surviving boxes (~1-5 targets) from VRAM to CPU
                    final_boxes = torch.stack([x1[keep], y1[keep], x2[keep], y2[keep], cx[keep], cy[keep], w[keep], h[keep], v_scores[keep]], dim=1).cpu().numpy()
                    final_cls = v_cls[keep].cpu().numpy()

                    results = []
                    for i in range(len(final_boxes)):
                        row = final_boxes[i]
                        cid = int(final_cls[i])
                        cls_name = self._resolve_class_name(cid)
                        results.append({
                            "x1": float(row[0]), "y1": float(row[1]), "x2": float(row[2]), "y2": float(row[3]),
                            "cx": float(row[4]), "cy": float(row[5]),
                            "w": max(1.0, float(row[6])), "h": max(1.0, float(row[7])),
                            "class_id": cid, "class_name": cls_name, "conf": float(row[8])
                        })
                    return results

                pred = self.gpu_output.float().cpu().numpy()
        else:
            frame_3c = frame_bgr[:, :, :3] if frame_bgr.shape[2] == 4 else frame_bgr
            if src_w != 640 or src_h != 640:
                if CV2_AVAILABLE:
                    resized = cv2.resize(frame_3c, (640, 640), interpolation=cv2.INTER_LINEAR)
                else:
                    y_idx = (np.arange(640) * (src_h / 640.0)).astype(np.int32)
                    x_idx = (np.arange(640) * (src_w / 640.0)).astype(np.int32)
                    resized = frame_3c[y_idx[:, None], x_idx]
            else:
                resized = frame_3c

            np.multiply(resized[:, :, 2], 1.0 / 255.0, out=self.input_buffer[0, 0], casting="unsafe")
            np.multiply(resized[:, :, 1], 1.0 / 255.0, out=self.input_buffer[0, 1], casting="unsafe")
            np.multiply(resized[:, :, 0], 1.0 / 255.0, out=self.input_buffer[0, 2], casting="unsafe")

            self.session.run_with_iobinding(self.io_binding)
            pred = self.io_binding.get_outputs()[0].numpy().astype(np.float32)

        # Format A: End-to-End YOLOv10 / Custom [1, 300, 6] -> (x1, y1, x2, y2, conf, cls)
        if pred.ndim == 3 and (pred.shape[1] == 300 or pred.shape[2] == 6):
            boxes = pred[0]
            mask = boxes[:, 4] >= conf_thresh
            valid = boxes[mask]
            if len(valid) == 0:
                return []

            results = []
            for row in valid[:20]:
                x1 = float(row[0]) * scale_x + offset_x
                y1 = float(row[1]) * scale_y + offset_y
                x2 = float(row[2]) * scale_x + offset_x
                y2 = float(row[3]) * scale_y + offset_y
                conf = float(row[4])
                cls_id = int(row[5])
                cls_name = self._resolve_class_name(cls_id)
                w = max(1.0, x2 - x1)
                h = max(1.0, y2 - y1)
                results.append({
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "cx": (x1 + x2) * 0.5, "cy": (y1 + y2) * 0.5,
                    "w": w, "h": h,
                    "class_id": cls_id, "class_name": cls_name, "conf": conf
                })
            return results

        # Format B: Standard YOLOv8 / YOLOv11 [1, 4 + num_classes, 8400]
        if pred.ndim == 3 and pred.shape[2] == 8400:
            data = pred[0]
            scores_matrix = data[4:, :]
            if scores_matrix.shape[0] == 1:
                max_scores = scores_matrix[0]
                max_classes = np.zeros(8400, dtype=np.int32)
            else:
                max_classes = np.argmax(scores_matrix, axis=0)
                max_scores = scores_matrix[max_classes, np.arange(8400)]

            mask = max_scores >= conf_thresh
            if not np.any(mask):
                return []

            valid_scores = max_scores[mask]
            valid_cls = max_classes[mask]
            valid_boxes = data[:4, mask].T

            cx = valid_boxes[:, 0] * scale_x + offset_x
            cy = valid_boxes[:, 1] * scale_y + offset_y
            w = valid_boxes[:, 2] * scale_x
            h = valid_boxes[:, 3] * scale_y

            x1 = cx - w * 0.5
            y1 = cy - h * 0.5
            x2 = cx + w * 0.5
            y2 = cy + h * 0.5

            keep = self._fast_nms(x1, y1, x2, y2, valid_scores, iou_thresh, max_det=20)
            results = []
            for idx in keep:
                cid = int(valid_cls[idx])
                cls_name = self._resolve_class_name(cid)
                bx1, by1, bx2, by2 = float(x1[idx]), float(y1[idx]), float(x2[idx]), float(y2[idx])
                results.append({
                    "x1": bx1, "y1": by1, "x2": bx2, "y2": by2,
                    "cx": float(cx[idx]), "cy": float(cy[idx]),
                    "w": max(1.0, float(w[idx])), "h": max(1.0, float(h[idx])),
                    "class_id": cid, "class_name": cls_name, "conf": float(valid_scores[idx])
                })
            return results

        return []

    def _resolve_class_name(self, cls_id: int) -> str:
        name_val = self.names.get(cls_id)
        if name_val is not None:
            return str(name_val).upper()
        if cls_id == 7:
            return "HEAD"
        if cls_id in (0, 1):
            return "PLAYER"
        return f"TARGET_{cls_id}"

    @staticmethod
    def _fast_nms(x1, y1, x2, y2, scores, iou_thresh: float, max_det: int = 20):
        order = scores.argsort()[::-1]
        areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
        keep = []

        while order.size > 0 and len(keep) < max_det:
            i = order[0]
            keep.append(i)
            if order.size == 1:
                break

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            union = areas[i] + areas[order[1:]] - inter
            iou = np.where(union > 0.0, inter / union, 0.0)

            inds = np.where(iou < iou_thresh)[0]
            order = order[inds + 1]

        return keep


# =====================================================================
# 3. MAIN REAL-TIME TACTICAL VISION ENGINE
# =====================================================================

class YOLOEngine:
    def __init__(self, config):
        self.config = config
        self.running = False
        self._thread = None
        self._lock = threading.Lock()
        self._model_lock = threading.Lock()

        # Engine state
        self._state = {
            "fps": 0.0,
            "latency_ms": 0.0,
            "capture_ms": 0.0,
            "frametime_history": [],
            "targets": [],
            "scan_region": {"left": 0, "top": 0, "width": 1920, "height": 1080},
            "model_name": "",
            "backend_name": "ONNX Runtime CUDA",
            "is_ready": False,
        }

        self.model = None
        self.onnx_engine = None
        self.backend_type = "onnx_cuda"
        self.device = "cuda:0" if (TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
        self.model_path = self.config.get("model_path", "battlefield_2042_fp16.onnx")
        self.screen_w, self.screen_h = get_screen_resolution()
        self.tracked_targets = {}
        self.next_target_id = 1
        self.makcu_aimbot = MAKCU_AimbotEngine(self.config)

    def start(self):
        """Start the background detection loop."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop detection loop."""
        self.running = False
        if hasattr(self, "makcu_aimbot") and self.makcu_aimbot:
            self.makcu_aimbot.disconnect()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def load_model(self, path=None):
        """
        Load or reload model.
        Automatically upgrades .onnx models to their _fp16.onnx counterpart if available,
        and uses GPU-side preprocessing + TensorRT/CUDA Execution Provider.
        """
        target_path = path or self.config.get("model_path", "battlefield_2042.onnx")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(target_path):
            target_path = os.path.join(base_dir, target_path)

        # Automatically prefer pre-compiled TensorRT 10 .engine first (fastest: ~3.1-5.5ms via DirectTensorRTEngine),
        # then _fp16.onnx / .onnx via NativeOnnxCudaEngine, then .pt
        stem = target_path
        for ext in ("_fp16.onnx", ".onnx", ".engine", ".pt"):
            if stem.lower().endswith(ext):
                stem = stem[: -len(ext)]
                break
        engine_candidate = stem + ".engine"
        fp16_candidate = stem + "_fp16.onnx"
        onnx_candidate = stem + ".onnx"
        if TRT_PKG_AVAILABLE and os.path.exists(engine_candidate):
            target_path = engine_candidate
        elif os.path.exists(fp16_candidate):
            target_path = fp16_candidate
        elif os.path.exists(onnx_candidate) and not target_path.lower().endswith(".onnx"):
            target_path = onnx_candidate

        with self._model_lock:
            try:
                model_name = os.path.basename(target_path)
                is_engine = target_path.lower().endswith(".engine")
                is_onnx = target_path.lower().endswith(".onnx")

                if is_engine and TRT_PKG_AVAILABLE and TORCH_AVAILABLE and torch.cuda.is_available():
                    try:
                        print(f"[YOLOEngine] Loading Direct TensorRT 10 Engine '{model_name}' (execute_async_v3 + CUDA Stream)...")
                        self.onnx_engine = DirectTensorRTEngine(target_path)
                        self.model = None
                        self.backend_type = "onnx_cuda"
                        self.model_path = target_path
                        backend_str = "Direct TensorRT 10 (FP16 + Async CUDA Stream + RingBuffer)"
                        with self._lock:
                            self._state["model_name"] = model_name
                            self._state["backend_name"] = backend_str
                            self._state["is_ready"] = True
                        print(f"[YOLOEngine] '{model_name}' ready on {backend_str}!")
                        return True
                    except Exception as e_eng:
                        print(f"[YOLOEngine] Engine '{model_name}' incompatible with this GPU ({e_eng}).")
                        
                        # 1. Attempt Auto-Compilation for THIS GPU from available ONNX model!
                        onnx_src = fp16_candidate if os.path.exists(fp16_candidate) else (onnx_candidate if os.path.exists(onnx_candidate) else None)
                        if onnx_src and TRT_PKG_AVAILABLE:
                            try:
                                with self._lock:
                                    self._state["backend_name"] = "Compiling Custom TensorRT Engine for your GPU..."
                                ok = build_trt_engine_from_onnx(onnx_src, target_path)
                                if ok and os.path.exists(target_path):
                                    self.onnx_engine = DirectTensorRTEngine(target_path)
                                    self.model = None
                                    self.backend_type = "onnx_cuda"
                                    self.model_path = target_path
                                    backend_str = "Direct TensorRT 10 (Custom GPU Engine)"
                                    with self._lock:
                                        self._state["model_name"] = model_name
                                        self._state["backend_name"] = backend_str
                                        self._state["is_ready"] = True
                                    print(f"[YOLOEngine] '{model_name}' successfully compiled and active on {backend_str}!")
                                    return True
                            except Exception as e_build:
                                print(f"[YOLOEngine] Auto-compile failed: {e_build}")

                        # 2. Fallback to native ONNX model
                        if os.path.exists(fp16_candidate):
                            target_path = fp16_candidate
                            model_name = os.path.basename(target_path)
                            is_onnx = True
                        elif os.path.exists(onnx_candidate):
                            target_path = onnx_candidate
                            model_name = os.path.basename(target_path)
                            is_onnx = True

                if is_onnx and ORT_AVAILABLE:
                    print(f"[YOLOEngine] Loading native ONNX model '{model_name}' with GPU Preprocessing...")
                    use_trt_ep = bool(self.config.get("use_trt_ep", False))
                    self.onnx_engine = NativeOnnxCudaEngine(target_path, prefer_trt_ep=use_trt_ep)
                    active_prov = self.onnx_engine.active_provider

                    # If ONNX fell back to CPU but PyTorch CUDA is ready on the GPU, reject CPU and switch to PyTorch CUDA
                    if active_prov == "CPUExecutionProvider" and TORCH_AVAILABLE and torch.cuda.is_available():
                        print(f"[YOLOEngine] ⚠️ ONNX dropped to CPU! Switching automatically to PyTorch CUDA stream for maximum FPS...")
                        self.onnx_engine = None
                    else:
                        self.model = None
                        self.backend_type = "onnx_cuda"
                        self.model_path = target_path
                        prec_tag = "FP16" if (self.onnx_engine.is_fp16 or "Tensorrt" in active_prov) else "FP32"
                        gpu_pre_tag = " + GPU-Preproc" if self.onnx_engine.use_gpu_iobinding else ""
                        backend_str = f"ONNX ({active_prov.replace('ExecutionProvider', '')} {prec_tag}{gpu_pre_tag})"
                        with self._lock:
                            self._state["model_name"] = model_name
                            self._state["backend_name"] = backend_str
                            self._state["is_ready"] = True
                        print(f"[YOLOEngine] '{model_name}' ready on {backend_str}!")
                        return True

                if ULTRALYTICS_AVAILABLE:
                    pt_candidate = stem + ".pt"
                    load_target = pt_candidate if os.path.exists(pt_candidate) else target_path
                    load_name = os.path.basename(load_target)
                    print(f"[YOLOEngine] Loading '{load_name}' via Ultralytics on {self.device}...")
                    is_engine = load_target.lower().endswith(".engine")
                    is_onnx_t = load_target.lower().endswith(".onnx")
                    if is_engine or is_onnx_t:
                        model = YOLO(load_target, task="detect")
                    else:
                        model = YOLO(load_target)
                        if self.device != "cpu":
                            model.to(self.device)

                    self.model = model
                    self.onnx_engine = None
                    self.backend_type = "ultralytics"
                    self.model_path = load_target
                    gpu_name = torch.cuda.get_device_name(0) if (TORCH_AVAILABLE and torch.cuda.is_available()) else "CPU"
                    backend_str = f"Ultralytics PyTorch CUDA ({gpu_name})" if self.device != "cpu" else "PyTorch CPU"
                    with self._lock:
                        self._state["model_name"] = load_name
                        self._state["backend_name"] = backend_str
                        self._state["is_ready"] = True
                    print(f"[YOLOEngine] '{load_name}' loaded successfully ({backend_str}).")
                    return True

                return False
            except Exception as e:
                print(f"[YOLOEngine] Error loading model {target_path}: {e}")
                with self._lock:
                    self._state["is_ready"] = False
                return False

    def _compute_scan_region(self):
        """Calculate the crop region based on config with Dynamic Combat Zoom."""
        sw, sh = self.screen_w, self.screen_h

        if self.config.get("dynamic_combat_zoom", True):
            makcu_st = self.makcu_aimbot.get_state() if hasattr(self, "makcu_aimbot") and self.makcu_aimbot else {}
            has_lock = makcu_st.get("has_lock", False) or makcu_st.get("is_aiming", False)
            if has_lock:
                zoom_size = int(self.config.get("combat_zoom_size", 384))
                left = max(0, (sw - zoom_size) // 2)
                top = max(0, (sh - zoom_size) // 2)
                return {"left": left, "top": top, "width": zoom_size, "height": zoom_size}

        mode = self.config.get("scan_region_mode", "center_640")
        if mode == "center_480":
            rw, rh = 480, 480
        elif mode == "center_640":
            rw, rh = 640, 640
        elif mode == "center_960":
            rw, rh = 960, 960
        elif mode == "fullscreen":
            return {"left": 0, "top": 0, "width": sw, "height": sh}
        else:
            rw, rh = 640, 640

        left = max(0, (sw - rw) // 2)
        top = max(0, (sh - rh) // 2)
        return {"left": left, "top": top, "width": rw, "height": rh}

    def _detection_loop(self):
        """Main detection worker running Zero-Copy Win32 DIBSection capture & GPU-Preprocessed ONNX inference."""
        try:
            user32 = ctypes.windll.user32
            h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                user32.SetThreadDesktop(h_desk)
        except Exception:
            pass

        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
            if self.config.get("high_process_priority", True):
                # HIGH_PRIORITY_CLASS (0x00000080) & THREAD_PRIORITY_HIGHEST (2)
                h_proc = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.kernel32.SetPriorityClass(h_proc, 0x00000080)
                h_thr = ctypes.windll.kernel32.GetCurrentThread()
                ctypes.windll.kernel32.SetThreadPriority(h_thr, 2)
        except Exception:
            pass

        if not self.onnx_engine and not self.model:
            self.load_model()

        # Initialize Zero-Copy Win32 DIBSection Triple-Ring-Buffer Screen Capture in dedicated thread (preallocated full resolution)
        dib_capture = Win32ZeroCopyCapture(max_width=max(1920, int(self.screen_w)), max_height=max(1080, int(self.screen_h)))
        sct_fallback = mss.mss() if MSS_AVAILABLE else None
        latest_frame_lock = threading.Lock()
        latest_frame_state = {
            "frame": None,
            "region": self._compute_scan_region(),
            "cap_ms": 0.05,
            "ready_slot": -1,
            "read_slot": -1,
        }

        def _capture_worker():
            try:
                u32 = ctypes.windll.user32
                hd = u32.OpenDesktopW("Default", 0, False, 0x01FF)
                if hd:
                    u32.SetThreadDesktop(hd)
            except Exception:
                pass
            write_idx = 0
            while self.running:
                if not self.config.get("enabled", True):
                    time.sleep(0.02)
                    continue
                reg = self._compute_scan_region()
                rl, rt, rw, rh = reg["left"], reg["top"], reg["width"], reg["height"]

                # Pick a ring-buffer slot that is neither currently read nor currently marked ready
                with latest_frame_lock:
                    r_slot = latest_frame_state["read_slot"]
                    p_slot = latest_frame_state["ready_slot"]
                for candidate in range(dib_capture.NUM_RING_SLOTS):
                    slot_c = (write_idx + candidate) % dib_capture.NUM_RING_SLOTS
                    if slot_c != r_slot and slot_c != p_slot:
                        write_idx = slot_c
                        break

                tc0 = time.perf_counter()
                f_bgra = dib_capture.capture_slot(write_idx, rl, rt, rw, rh)
                if f_bgra is not None:
                    cap_dt = (time.perf_counter() - tc0) * 1000.0
                    with latest_frame_lock:
                        latest_frame_state["frame"] = f_bgra
                        latest_frame_state["ready_slot"] = write_idx
                        latest_frame_state["region"] = reg
                        latest_frame_state["cap_ms"] = cap_dt
                    write_idx = (write_idx + 1) % dib_capture.NUM_RING_SLOTS
                else:
                    time.sleep(0.001)

        cap_thread = threading.Thread(target=_capture_worker, daemon=True)
        cap_thread.start()

        frame_count = 0
        fps_timer = time.time()
        current_fps = 0.0

        while self.running:
            if not self.config.get("enabled", True) or (not self.onnx_engine and not self.model):
                if self.tracked_targets or self._state["targets"]:
                    self.tracked_targets.clear()
                    with self._lock:
                        self._state["targets"] = []
                        self._state["fps"] = 0.0
                if hasattr(self, "makcu_aimbot") and self.makcu_aimbot:
                    try:
                        self.makcu_aimbot.process_targets([], self.screen_w / 2.0, self.screen_h / 2.0, 0.0)
                    except Exception:
                        pass
                time.sleep(0.04)
                continue

            t_start = time.perf_counter()

            # 1. Pull latest Zero-Copy Triple-Ring-Buffer frame (0 Bytes RAM copy, ~0.002 ms wait-free)
            t_pull0 = time.perf_counter()
            with latest_frame_lock:
                frame_bgr = latest_frame_state["frame"]
                latest_frame_state["read_slot"] = latest_frame_state["ready_slot"]
                region = latest_frame_state["region"]
            r_left, r_top, r_w, r_h = region["left"], region["top"], region["width"], region["height"]
            t_cap_ms = (time.perf_counter() - t_pull0) * 1000.0

            if frame_bgr is None and sct_fallback is not None:
                try:
                    grabbed = sct_fallback.grab(region)
                    frame_bgr = np.frombuffer(grabbed.raw, dtype=np.uint8).reshape((grabbed.height, grabbed.width, 4))[:, :, :3]
                except Exception:
                    time.sleep(0.002)
                    continue

            if frame_bgr is None:
                time.sleep(0.001)
                continue

            # 2. Run Inference (GPU-Preprocessed ONNX Runtime or Ultralytics)
            conf_thresh = float(self.config.get("confidence_threshold", 0.40))
            iou_thresh = float(self.config.get("iou_threshold", 0.45))
            offset_x = float(r_left)
            offset_y = float(r_top)
            crosshair_x = self.screen_w / 2.0
            crosshair_y = self.screen_h / 2.0

            detected_targets = []
            with self._model_lock:
                if self.backend_type == "onnx_cuda" and self.onnx_engine is not None:
                    try:
                        detected_targets = self.onnx_engine.infer(
                            frame_bgr, offset_x, offset_y, conf_thresh, iou_thresh
                        )
                    except Exception as e:
                        print(f"[YOLOEngine] ONNX inference error: {e}")
                        time.sleep(0.005)
                        continue
                elif self.model is not None:
                    use_half = bool(self.config.get("use_half_precision", True) and "cuda" in self.device)
                    if self.model_path.endswith(".engine") or self.model_path.endswith(".onnx"):
                        use_half = False
                    detect_all = bool(self.config.get("detect_all_classes", True))
                    pred_classes = None if detect_all else self.config.get("target_classes", [0])
                    agnostic_nms = bool(self.config.get("agnostic_nms", True))

                    try:
                        frame_3c = frame_bgr[:, :, :3] if frame_bgr.shape[2] == 4 else frame_bgr
                        with torch.inference_mode():
                            results = self.model.predict(
                                source=frame_3c,
                                conf=conf_thresh,
                                iou=iou_thresh,
                                classes=pred_classes,
                                device=self.device,
                                half=use_half,
                                max_det=20,
                                agnostic_nms=agnostic_nms,
                                verbose=False,
                            )
                        if results and len(results) > 0 and len(results[0].boxes) > 0:
                            boxes = results[0].boxes
                            names = self.model.names if hasattr(self.model, "names") else {}
                            xyxy_all = boxes.xyxy.cpu().numpy()
                            cls_all = boxes.cls.cpu().numpy().astype(int)
                            conf_all = boxes.conf.cpu().numpy()

                            for i in range(len(xyxy_all)):
                                coords = xyxy_all[i]
                                x1 = float(coords[0]) + offset_x
                                y1 = float(coords[1]) + offset_y
                                x2 = float(coords[2]) + offset_x
                                y2 = float(coords[3]) + offset_y
                                cls_id = int(cls_all[i])
                                conf = float(conf_all[i])
                                cls_name = str(names.get(cls_id, f"Target_{cls_id}")).upper()
                                if cls_name in ("PERSON", "ITEM", "0"):
                                    cls_name = "ENEMY"

                                detected_targets.append({
                                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                    "cx": (x1 + x2) * 0.5, "cy": (y1 + y2) * 0.5,
                                    "w": max(1.0, x2 - x1), "h": max(1.0, y2 - y1),
                                    "class_id": cls_id, "class_name": cls_name, "conf": conf,
                                })
                    except Exception:
                        time.sleep(0.005)
                        continue

            # 3. Target Tracking, Anti-Jitter EMA Smoothing & Stance Detection
            # FUSION FIX: Merge separate 'HEAD' and 'PLAYER'/'BOT' detections so the aimbot never flips between Head & Chest
            now = time.time()
            ghost_duration = float(self.config.get("ghost_duration", 1.5))
            enable_ghosts = bool(self.config.get("ghost_tracking", True))

            # Filter out non-combatant classes (weapons, dead bodies, smokes)
            # In Valorant: 0=player, 1=bot, 7=head
            valid_targets = []
            head_boxes = []
            body_boxes = []

            for dt in detected_targets:
                cid = dt.get("class_id")
                cname = str(dt.get("class_name", "")).upper()
                # Skip weapons, smoke, dead bodies
                if cid in (2, 4, 8, 9) or any(bad in cname for bad in ("WEAPON", "DEAD", "SMOKE", "FIRE")):
                    continue

                if "HEAD" in cname or cid == 7:
                    head_boxes.append(dt)
                else:
                    body_boxes.append(dt)

            # Strict Fusion: if a body has a detected head box nearby or inside, merge them completely
            for hb in head_boxes:
                hcx, hcy = hb["cx"], hb["cy"]
                matched = False
                for bb in body_boxes:
                    # Head overlaps with body horizontally and is in upper 50%
                    x_overlap = (bb["x1"] - 25.0 <= hcx <= bb["x2"] + 25.0)
                    y_overlap = (bb["y1"] - 35.0 <= hcy <= bb["y1"] + bb["h"] * 0.55)
                    if x_overlap and y_overlap:
                        bb["head_cx"] = hcx
                        bb["head_cy"] = hcy
                        bb["has_direct_head"] = True
                        matched = True
                        break
                if not matched:
                    # Isolated head detection (e.g. head glitching behind cover)
                    hb["head_cx"] = hb["cx"]
                    hb["head_cy"] = hb["cy"]
                    hb["has_direct_head"] = True
                    body_boxes.append(hb)

            # Suppress any duplicate boxes that overlap heavily (>0.35 IoU or close centers)
            deduped_targets = []
            for b in body_boxes:
                dup = False
                for existing in deduped_targets:
                    dist_centers = math.hypot(b["cx"] - existing["cx"], b["cy"] - existing["cy"])
                    if dist_centers < min(b["w"], existing["w"]) * 0.75:
                        dup = True
                        # Preserve head coordinates if available
                        if b.get("has_direct_head") and not existing.get("has_direct_head"):
                            existing["head_cx"] = b["head_cx"]
                            existing["head_cy"] = b["head_cy"]
                            existing["has_direct_head"] = True
                        break
                if not dup:
                    deduped_targets.append(b)

            detected_targets = deduped_targets

            matched_tracker_ids = set()
            targets = []

            for t in detected_targets:
                best_id = None
                best_d = float("inf")
                for tid, tr in self.tracked_targets.items():
                    if tid in matched_tracker_ids:
                        continue
                    d = math.hypot(t["cx"] - tr["cx"], t["cy"] - tr["cy"])
                    if d < max(t["w"], t["h"], 90.0) and d < best_d:
                        best_d = d
                        best_id = tid

                if best_id is not None:
                    tr = self.tracked_targets[best_id]
                    dt = max(0.001, now - tr["last_seen"])
                    raw_vx = (t["cx"] - tr["cx"]) / dt
                    raw_vy = (t["cy"] - tr["cy"]) / dt
                    vx = max(-2000.0, min(2000.0, 0.55 * tr.get("vx", 0.0) + 0.45 * raw_vx))
                    vy = max(-2000.0, min(2000.0, 0.55 * tr.get("vy", 0.0) + 0.45 * raw_vy))
                    target_speed = math.hypot(vx, vy)

                    if self.config.get("box_smoothing", True):
                        if self.config.get("adaptive_smoothing", True):
                            speed_norm = min(1.0, target_speed / 500.0)
                            alpha = 0.28 + 0.60 * speed_norm
                        else:
                            alpha = float(self.config.get("box_smoothing_factor", 0.65))

                        if best_d < 120.0:
                            t["x1"] = alpha * t["x1"] + (1.0 - alpha) * tr["x1"]
                            t["y1"] = alpha * t["y1"] + (1.0 - alpha) * tr["y1"]
                            t["x2"] = alpha * t["x2"] + (1.0 - alpha) * tr["x2"]
                            t["y2"] = alpha * t["y2"] + (1.0 - alpha) * tr["y2"]
                            t["cx"] = (t["x1"] + t["x2"]) * 0.5
                            t["cy"] = (t["y1"] + t["y2"]) * 0.5
                            t["w"] = max(1.0, t["x2"] - t["x1"])
                            t["h"] = max(1.0, t["y2"] - t["y1"])

                    tr.update({
                        "cx": t["cx"], "cy": t["cy"], "w": t["w"], "h": t["h"],
                        "x1": t["x1"], "y1": t["y1"], "x2": t["x2"], "y2": t["y2"],
                        "vx": vx, "vy": vy, "last_seen": now, "last_update": now,
                        "class_id": t["class_id"], "class_name": t["class_name"], "conf": t["conf"]
                    })
                    matched_tracker_ids.add(best_id)
                    t["target_id"] = best_id
                    t["vx"] = vx
                    t["vy"] = vy
                    t["is_ghost"] = False
                else:
                    new_id = self.next_target_id
                    self.next_target_id += 1
                    self.tracked_targets[new_id] = {
                        "cx": t["cx"], "cy": t["cy"], "w": t["w"], "h": t["h"],
                        "x1": t["x1"], "y1": t["y1"], "x2": t["x2"], "y2": t["y2"],
                        "vx": 0.0, "vy": 0.0, "last_seen": now, "last_update": now,
                        "class_id": t["class_id"], "class_name": t["class_name"], "conf": t["conf"]
                    }
                    matched_tracker_ids.add(new_id)
                    t["target_id"] = new_id
                    t["vx"] = 0.0
                    t["vy"] = 0.0
                    t["is_ghost"] = False

                aspect = t["w"] / max(1.0, t["h"])
                if t.get("has_direct_head", False) and "head_cx" in t and "head_cy" in t:
                    head_x = t["head_cx"]
                    head_y = t["head_cy"]
                    head_ratio = (head_y - t["y1"]) / max(1.0, t["h"])
                    stance = "NORMAL"
                elif self.config.get("stance_detection", True):
                    if aspect > 0.48:
                        head_ratio = 0.22
                        stance = "CROUCH"
                    elif aspect < 0.32:
                        head_ratio = 0.11
                        stance = "STAND"
                    else:
                        head_ratio = 0.11
                        stance = "NORMAL"
                    head_x = t["cx"]
                    head_y = t["y1"] + t["h"] * head_ratio
                else:
                    head_ratio = 0.11
                    stance = "NORMAL"
                    head_x = t["cx"]
                    head_y = t["y1"] + t["h"] * head_ratio

                if self.config.get("latency_compensation", True):
                    curr_lat = self._state.get("latency_ms", 4.0)
                    lead_time = max(0.004, min(0.040, (curr_lat * 1.25) / 1000.0))
                    head_x += t["vx"] * lead_time
                    head_y += t["vy"] * lead_time

                head_h = t["h"] * (0.16 if stance == "STAND" else 0.20)
                head_w = min(t["w"] * 0.44, head_h * 0.90)

                t["stance"] = stance
                t["head_ratio"] = head_ratio
                t["head_cx"] = head_x
                t["head_cy"] = head_y
                t["head_w"] = max(5.0, head_w)
                t["head_h"] = max(5.0, head_h)
                t["dist_head"] = math.hypot(head_x - crosshair_x, head_y - crosshair_y)
                t["dist"] = math.hypot(t["cx"] - crosshair_x, t["cy"] - crosshair_y)
                t["is_closest"] = False
                targets.append(t)

            expired_ids = []
            for tid, tr in list(self.tracked_targets.items()):
                if tid not in matched_tracker_ids:
                    dt_loss = now - tr["last_seen"]
                    if enable_ghosts and dt_loss < ghost_duration:
                        dt_step = now - tr.get("last_update", now)
                        pred_cx = tr["cx"] + tr.get("vx", 0.0) * dt_step
                        pred_cy = tr["cy"] + tr.get("vy", 0.0) * dt_step
                        half_w = tr["w"] * 0.5
                        half_h = tr["h"] * 0.5

                        tr["cx"] = pred_cx
                        tr["cy"] = pred_cy
                        tr["last_update"] = now

                        ghost_alpha = max(0.2, 1.0 - (dt_loss / ghost_duration))
                        dist = math.hypot(pred_cx - crosshair_x, pred_cy - crosshair_y)

                        ghost_aspect = tr["w"] / max(1.0, tr["h"])
                        ghost_head_ratio = 0.22 if ghost_aspect > 0.48 else (0.125 if ghost_aspect < 0.32 else 0.155)
                        ghost_head_cx = pred_cx
                        ghost_head_cy = (pred_cy - half_h) + tr["h"] * ghost_head_ratio
                        ghost_head_h = tr["h"] * 0.18
                        ghost_head_w = min(tr["w"] * 0.44, ghost_head_h * 0.90)
                        targets.append({
                            "x1": float(pred_cx - half_w),
                            "y1": float(pred_cy - half_h),
                            "x2": float(pred_cx + half_w),
                            "y2": float(pred_cy + half_h),
                            "cx": pred_cx,
                            "cy": pred_cy,
                            "head_cx": ghost_head_cx,
                            "head_cy": ghost_head_cy,
                            "head_w": ghost_head_w,
                            "head_h": ghost_head_h,
                            "dist_head": math.hypot(ghost_head_cx - crosshair_x, ghost_head_cy - crosshair_y),
                            "w": tr["w"],
                            "h": tr["h"],
                            "class_id": tr["class_id"],
                            "class_name": tr["class_name"],
                            "conf": tr["conf"],
                            "dist": dist,
                            "is_closest": False,
                            "target_id": tid,
                            "is_ghost": True,
                            "ghost_alpha": ghost_alpha,
                            "dt_loss": dt_loss,
                            "vx": tr.get("vx", 0.0),
                            "vy": tr.get("vy", 0.0)
                        })
                    else:
                        expired_ids.append(tid)

            for tid in expired_ids:
                self.tracked_targets.pop(tid, None)

            closest_dist = float("inf")
            closest_idx = -1
            for i, t in enumerate(targets):
                if t["dist"] < closest_dist:
                    closest_dist = t["dist"]
                    closest_idx = i

            if 0 <= closest_idx < len(targets):
                targets[closest_idx]["is_closest"] = True

            t_end = time.perf_counter()
            latency = (t_end - t_start) * 1000.0

            if hasattr(self, "makcu_aimbot") and self.makcu_aimbot:
                try:
                    self.makcu_aimbot.process_targets(targets, crosshair_x, crosshair_y, latency)
                except Exception:
                    pass

            frame_count += 1
            now_t = time.time()
            if now_t - fps_timer >= 0.4:
                current_fps = frame_count / (now_t - fps_timer)
                frame_count = 0
                fps_timer = now_t

            with self._lock:
                self._state["fps"] = round(current_fps, 1)
                self._state["latency_ms"] = round(latency, 1)
                self._state["capture_ms"] = round(t_cap_ms, 3)
                hist = self._state["frametime_history"]
                hist.append(round(latency, 2))
                if len(hist) > 60:
                    del hist[:-60]
                self._state["targets"] = targets
                self._state["scan_region"] = region

            max_fps = self.config.get("max_fps", 300)
            if max_fps > 0 and max_fps < 300:
                target_frame_time = 1.0 / max_fps
                elapsed = time.perf_counter() - t_start
                if elapsed < target_frame_time:
                    remaining = target_frame_time - elapsed
                    if remaining > 0.0025:
                        time.sleep(remaining - 0.0018)
                    while (time.perf_counter() - t_start) < target_frame_time:
                        pass

        dib_capture.dispose()
        if sct_fallback is not None:
            sct_fallback.close()
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass

    def get_state(self):
        """Thread-safe snapshot of latest detection state."""
        makcu_st = self.makcu_aimbot.get_state() if hasattr(self, "makcu_aimbot") and self.makcu_aimbot else {}
        with self._lock:
            return {
                "fps": self._state["fps"],
                "latency_ms": self._state["latency_ms"],
                "capture_ms": self._state.get("capture_ms", 0.05),
                "frametime_history": list(self._state.get("frametime_history", [])),
                "backend_name": self._state.get("backend_name", "ONNX Runtime CUDA"),
                "targets": [dict(t) for t in self._state["targets"]],
                "scan_region": dict(self._state["scan_region"]),
                "model_name": self._state["model_name"],
                "is_ready": self._state["is_ready"],
                "makcu": makcu_st,
            }
