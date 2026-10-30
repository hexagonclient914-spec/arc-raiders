using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows;
using System.Windows.Interop;

namespace YoloTacticalVisionCS;

public partial class App : Application
{
    [DllImport("winmm.dll", EntryPoint = "timeBeginPeriod")]
    private static extern uint TimeBeginPeriod(uint uMilliseconds);

    [DllImport("winmm.dll", EntryPoint = "timeEndPeriod")]
    private static extern uint TimeEndPeriod(uint uMilliseconds);

    private YoloConfig _config = null!;
    private YoloInferenceEngine _engine = null!;
    private TargetTracker _tracker = null!;
    private ScreenCapture _capture = null!;
    private OverlayWindow _overlay = null!;
    private SettingsWindow _settings = null!;
    private HotkeyManager? _hotkeys;

    private Thread? _workerThread;
    private volatile bool _running = true;

    private static void Log(string msg)
    {
        try
        {
            string logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "startup.log");
            File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] {msg}\n");
        }
        catch { }
    }

    public App()
    {
        ShutdownMode = ShutdownMode.OnExplicitShutdown;
    }

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        Log("OnStartup began");

        AppDomain.CurrentDomain.UnhandledException += (s, ev) =>
        {
            File.WriteAllText("crash.log", ev.ExceptionObject.ToString());
        };

        DispatcherUnhandledException += (s, ev) =>
        {
            File.WriteAllText("crash_dispatcher.log", ev.Exception.ToString());
            ev.Handled = true;
        };

        try { TimeBeginPeriod(1); } catch { }

        Log("Loading config...");
        _config = YoloConfig.Load();

        Log("Creating engine & tracker...");
        _engine = new YoloInferenceEngine();
        _tracker = new TargetTracker();
        _capture = new ScreenCapture(640, 640);

        Log("Creating overlay window...");
        _overlay = new OverlayWindow(_config);
        _overlay.Show();

        Log("Creating settings window...");
        _settings = new SettingsWindow(_config, _engine, _overlay);
        _settings.Topmost = true;
        _settings.Show();
        _settings.Activate();
        MainWindow = _settings;

        Log("Registering hotkeys...");
        try
        {
            var helper = new WindowInteropHelper(_overlay);
            IntPtr hwnd = helper.EnsureHandle();
            _hotkeys = new HotkeyManager(hwnd);
            _hotkeys.OnF7Pressed += () =>
            {
                Dispatcher.Invoke(() =>
                {
                    if (_overlay.Visibility == Visibility.Visible)
                        _overlay.Hide();
                    else
                        _overlay.Show();
                });
            };
            _hotkeys.OnF8Pressed += () =>
            {
                Dispatcher.Invoke(() =>
                {
                    if (_settings.Visibility == Visibility.Visible)
                        _settings.Hide();
                    else
                    {
                        _settings.Topmost = true;
                        _settings.Show();
                        _settings.Activate();
                    }
                });
            };
        }
        catch (Exception ex)
        {
            Log($"Hotkey registration warning: {ex.Message}");
        }

        Log($"Loading model {_config.ModelPath}...");
        _engine.LoadModel(_config.ModelPath);

        Log("Starting worker thread...");
        _workerThread = new Thread(DetectionLoop)
        {
            IsBackground = true,
            Priority = ThreadPriority.Highest
        };
        _workerThread.Start();
        Log("OnStartup completed successfully!");
    }

    private void DetectionLoop()
    {
        int screenW = (int)SystemParameters.PrimaryScreenWidth;
        int screenH = (int)SystemParameters.PrimaryScreenHeight;
        if (screenW <= 0) screenW = 1920;
        if (screenH <= 0) screenH = 1080;

        float screenCx = screenW / 2f;
        float screenCy = screenH / 2f;

        var fpsTimer = Stopwatch.StartNew();
        int frameCount = 0;
        float currentFps = 0f;
        float currentLatency = 0f;

        Log("DetectionLoop running");

        while (_running)
        {
            if (!_config.Enabled || !_engine.IsReady)
            {
                Thread.Sleep(20);
                continue;
            }

            var sw = Stopwatch.StartNew();

            int rw = 640, rh = 640;
            if (_config.ScanRegionMode == "center_480")
            {
                rw = 480;
                rh = 480;
            }
            else if (_config.ScanRegionMode == "fullscreen")
            {
                rw = screenW;
                rh = screenH;
            }

            int left = Math.Max(0, (screenW - rw) / 2);
            int top = Math.Max(0, (screenH - rh) / 2);

            _capture.Resize(rw, rh);

            if (!_capture.Capture(left, top, rw, rh))
            {
                Thread.Sleep(2);
                continue;
            }

            var rawDetections = _engine.Detect(
                _capture.BufferPtr,
                rw,
                rh,
                left,
                top,
                _config.ConfidenceThreshold,
                _config.IouThreshold);

            var trackedTargets = _tracker.Update(
                rawDetections,
                _config,
                screenCx,
                screenCy,
                currentLatency);

            sw.Stop();
            currentLatency = (float)sw.Elapsed.TotalMilliseconds;

            var scanRect = new Rect(left, top, rw, rh);
            _overlay.UpdateFrame(trackedTargets, scanRect, currentFps, currentLatency, _engine.ModelName);

            frameCount++;
            if (fpsTimer.ElapsedMilliseconds >= 300)
            {
                currentFps = (float)(frameCount / fpsTimer.Elapsed.TotalSeconds);
                frameCount = 0;
                fpsTimer.Restart();

                _settings.UpdateMetrics(currentFps, currentLatency, trackedTargets.Count);
            }

            int targetFps = Math.Clamp(_config.MaxFps, 60, 360);
            double targetMs = 1000.0 / targetFps;
            double elapsed = sw.Elapsed.TotalMilliseconds;
            if (elapsed < targetMs)
            {
                int sleepMs = (int)(targetMs - elapsed);
                if (sleepMs > 0) Thread.Sleep(sleepMs);
            }
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _running = false;
        try { _workerThread?.Join(500); } catch { }
        try { TimeEndPeriod(1); } catch { }
        _hotkeys?.Dispose();
        _capture?.Dispose();
        _engine?.Dispose();

        base.OnExit(e);
    }
}
