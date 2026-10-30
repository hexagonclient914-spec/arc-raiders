using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;

namespace YoloTacticalVisionCS;

public class YoloInferenceEngine : IDisposable
{
    private InferenceSession? _session;
    private string _currentModelPath = "";
    private readonly object _lock = new();

    private readonly float[] _inputBuffer = new float[1 * 3 * 640 * 640];
    private DenseTensor<float>? _inputTensor;
    private string _inputName = "images";

    public bool IsReady => _session != null;
    public string ModelName => Path.GetFileName(_currentModelPath);

    public bool LoadModel(string modelPath)
    {
        lock (_lock)
        {
            try
            {
                // Resolve path
                string fullPath = modelPath;
                if (!Path.IsPathRooted(fullPath))
                {
                    fullPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, modelPath);
                    if (!File.Exists(fullPath))
                    {
                        // Check parent folder if running from build directory
                        string altPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", modelPath);
                        if (File.Exists(altPath)) fullPath = Path.GetFullPath(altPath);
                    }
                }

                if (!File.Exists(fullPath))
                {
                    Console.WriteLine($"[Engine] Model file not found: {fullPath}");
                    return false;
                }

                _session?.Dispose();
                _session = null;

                var options = new SessionOptions();
                try
                {
                    options.AppendExecutionProvider_DML(0); // NVIDIA RTX GPU
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[Engine] DML fallback to CPU: {ex.Message}");
                }

                _session = new InferenceSession(fullPath, options);
                _currentModelPath = fullPath;
                _inputName = _session.InputNames[0];

                _inputTensor = new DenseTensor<float>(_inputBuffer, new int[] { 1, 3, 640, 640 });

                Console.WriteLine($"[Engine] Loaded {Path.GetFileName(fullPath)} successfully with DirectML!");
                return true;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[Engine] Error loading model: {ex.Message}");
                return false;
            }
        }
    }

    public unsafe List<DetectedTarget> Detect(IntPtr pBgraBits, int srcWidth, int srcHeight, float offsetX, float offsetY, float confThreshold, float iouThreshold)
    {
        lock (_lock)
        {
            if (_session == null || _inputTensor == null || pBgraBits == IntPtr.Zero)
                return new List<DetectedTarget>();

            // Preprocessing: Convert BGRA to RGB Float Tensor [1, 3, 640, 640]
            byte* pSrc = (byte*)pBgraBits.ToPointer();
            int planeSize = 640 * 640;

            fixed (float* pDst = _inputBuffer)
            {
                float* pR = pDst;
                float* pG = pDst + planeSize;
                float* pB = pDst + (planeSize * 2);

                float scaleX = (float)srcWidth / 640f;
                float scaleY = (float)srcHeight / 640f;

                for (int y = 0; y < 640; y++)
                {
                    int srcY = (int)(y * scaleY);
                    if (srcY >= srcHeight) srcY = srcHeight - 1;
                    byte* pRow = pSrc + (srcY * srcWidth * 4);

                    int rowOffset = y * 640;

                    for (int x = 0; x < 640; x++)
                    {
                        int srcX = (int)(x * scaleX);
                        if (srcX >= srcWidth) srcX = srcWidth - 1;

                        byte* pPixel = pRow + (srcX * 4);
                        int idx = rowOffset + x;

                        pR[idx] = pPixel[2] * (1f / 255f); // Red
                        pG[idx] = pPixel[1] * (1f / 255f); // Green
                        pB[idx] = pPixel[0] * (1f / 255f); // Blue
                    }
                }
            }

            // Run inference
            var inputs = new NamedOnnxValue[] { NamedOnnxValue.CreateFromTensor(_inputName, _inputTensor) };
            using var results = _session.Run(inputs);

            var outputValue = results[0];
            var tensor = outputValue.AsTensor<float>();
            var dims = tensor.Dimensions;

            var candidates = new List<DetectedTarget>();
            float scaleOutX = (float)srcWidth / 640f;
            float scaleOutY = (float)srcHeight / 640f;

            // Format A: YOLOv10 End-to-End [1, 300, 6]
            if (dims.Length == 3 && (dims[1] == 300 || dims[2] == 6))
            {
                int numBoxes = dims[1];
                for (int i = 0; i < numBoxes; i++)
                {
                    float conf = tensor[0, i, 4];
                    if (conf < confThreshold) continue;

                    float x1 = tensor[0, i, 0] * scaleOutX + offsetX;
                    float y1 = tensor[0, i, 1] * scaleOutY + offsetY;
                    float x2 = tensor[0, i, 2] * scaleOutX + offsetX;
                    float y2 = tensor[0, i, 3] * scaleOutY + offsetY;
                    int clsId = (int)tensor[0, i, 5];

                    candidates.Add(new DetectedTarget
                    {
                        X1 = x1,
                        Y1 = y1,
                        X2 = x2,
                        Y2 = y2,
                        Cx = (x1 + x2) / 2f,
                        Cy = (y1 + y2) / 2f,
                        Width = MathF.Max(1f, x2 - x1),
                        Height = MathF.Max(1f, y2 - y1),
                        Confidence = conf,
                        ClassId = clsId,
                        ClassName = clsId == 0 ? "RAIDER" : $"TARGET_{clsId}"
                    });
                }
                return candidates;
            }

            // Format B: Standard YOLOv8/11 [1, Channels, 8400]
            if (dims.Length == 3 && dims[2] == 8400)
            {
                int numChannels = dims[1];
                int numAnchors = dims[2];
                int numClasses = numChannels - 4;

                for (int i = 0; i < numAnchors; i++)
                {
                    // Find max class score
                    float maxScore = 0f;
                    int maxCls = 0;

                    for (int c = 0; c < numClasses; c++)
                    {
                        float score = tensor[0, 4 + c, i];
                        if (score > maxScore)
                        {
                            maxScore = score;
                            maxCls = c;
                        }
                    }

                    if (maxScore >= confThreshold)
                    {
                        float cx = tensor[0, 0, i] * scaleOutX + offsetX;
                        float cy = tensor[0, 1, i] * scaleOutY + offsetY;
                        float w = tensor[0, 2, i] * scaleOutX;
                        float h = tensor[0, 3, i] * scaleOutY;

                        float x1 = cx - w / 2f;
                        float y1 = cy - h / 2f;
                        float x2 = cx + w / 2f;
                        float y2 = cy + h / 2f;

                        candidates.Add(new DetectedTarget
                        {
                            X1 = x1,
                            Y1 = y1,
                            X2 = x2,
                            Y2 = y2,
                            Cx = cx,
                            Cy = cy,
                            Width = w,
                            Height = h,
                            Confidence = maxScore,
                            ClassId = maxCls,
                            ClassName = maxCls == 0 ? "RAIDER" : $"TARGET_{maxCls}"
                        });
                    }
                }

                return ApplyNMS(candidates, iouThreshold);
            }

            return candidates;
        }
    }

    private static List<DetectedTarget> ApplyNMS(List<DetectedTarget> boxes, float iouThresh)
    {
        boxes.Sort((a, b) => b.Confidence.CompareTo(a.Confidence));
        var result = new List<DetectedTarget>();
        var suppressed = new bool[boxes.Count];

        for (int i = 0; i < boxes.Count; i++)
        {
            if (suppressed[i]) continue;

            var a = boxes[i];
            result.Add(a);
            if (result.Count >= 20) break;

            for (int j = i + 1; j < boxes.Count; j++)
            {
                if (suppressed[j]) continue;

                var b = boxes[j];
                float interX1 = MathF.Max(a.X1, b.X1);
                float interY1 = MathF.Max(a.Y1, b.Y1);
                float interX2 = MathF.Min(a.X2, b.X2);
                float interY2 = MathF.Min(a.Y2, b.Y2);

                float interW = MathF.Max(0f, interX2 - interX1);
                float interH = MathF.Max(0f, interY2 - interY1);
                float interArea = interW * interH;

                float areaA = a.Width * a.Height;
                float areaB = b.Width * b.Height;
                float unionArea = areaA + areaB - interArea;

                float iou = unionArea > 0f ? interArea / unionArea : 0f;
                if (iou >= iouThresh)
                {
                    suppressed[j] = true;
                }
            }
        }

        return result;
    }

    public void Dispose()
    {
        lock (_lock)
        {
            _session?.Dispose();
            _session = null;
        }
    }
}
