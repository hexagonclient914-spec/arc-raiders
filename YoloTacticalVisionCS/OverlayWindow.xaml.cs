using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;

namespace YoloTacticalVisionCS;

public class OverlayCanvas : FrameworkElement
{
    private readonly OverlayWindow _window;
    public OverlayCanvas(OverlayWindow window)
    {
        _window = window;
        IsHitTestVisible = false;
    }

    protected override void OnRender(DrawingContext dc)
    {
        base.OnRender(dc);
        _window.RenderOverlay(dc);
    }
}

public partial class OverlayWindow : Window
{
    [DllImport("user32.dll")]
    private static extern int GetWindowLong(IntPtr hwnd, int index);

    [DllImport("user32.dll")]
    private static extern int SetWindowLong(IntPtr hwnd, int index, int newStyle);

    private const int GWL_EXSTYLE = -20;
    private const int WS_EX_TRANSPARENT = 0x00000020;
    private const int WS_EX_LAYERED = 0x00080000;
    private const int WS_EX_NOACTIVATE = 0x08000000;
    private const int WS_EX_TOOLWINDOW = 0x00000080;

    public YoloConfig Config { get; set; }

    private readonly OverlayCanvas _canvas;
    private List<DetectedTarget> _targets = new();
    private Rect _scanRegion = new(0, 0, 640, 640);
    private float _fps = 0;
    private float _latencyMs = 0;
    private string _modelName = "";

    // Brushes & Pens
    private readonly Typeface _consolasBold = new(new FontFamily("Consolas"), FontStyles.Normal, FontWeights.Bold, FontStretches.Normal);
    private readonly Typeface _segoeUi = new(new FontFamily("Segoe UI"), FontStyles.Normal, FontWeights.Bold, FontStretches.Normal);

    public OverlayWindow(YoloConfig config)
    {
        InitializeComponent();
        Config = config;

        Width = SystemParameters.PrimaryScreenWidth;
        Height = SystemParameters.PrimaryScreenHeight;

        _canvas = new OverlayCanvas(this);
        RootGrid.Children.Add(_canvas);

        Loaded += (_, _) => MakeClickThrough();
    }

    private void MakeClickThrough()
    {
        var hwnd = new WindowInteropHelper(this).EnsureHandle();
        int style = GetWindowLong(hwnd, GWL_EXSTYLE);
        SetWindowLong(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW);
    }

    public void UpdateFrame(List<DetectedTarget> targets, Rect scanRegion, float fps, float latencyMs, string modelName)
    {
        _targets = targets;
        _scanRegion = scanRegion;
        _fps = fps;
        _latencyMs = latencyMs;
        _modelName = modelName;

        Dispatcher.InvokeAsync(() => _canvas.InvalidateVisual(), System.Windows.Threading.DispatcherPriority.Render);
    }

    public void RenderOverlay(DrawingContext dc)
    {
        if (!Config.Enabled) return;

        double screenW = ActualWidth;
        double screenH = ActualHeight;
        if (screenW <= 0) screenW = SystemParameters.PrimaryScreenWidth;
        if (screenH <= 0) screenH = SystemParameters.PrimaryScreenHeight;

        double cx = screenW / 2.0;
        double cy = screenH / 2.0;

        // Check if any target or head is locked
        bool isOnTarget = false;
        bool isHeadLocked = false;
        foreach (var t in _targets)
        {
            if (t.X1 <= cx && cx <= t.X2 && t.Y1 <= cy && cy <= t.Y2)
            {
                isOnTarget = true;
                if (t.IsHeadLocked) isHeadLocked = true;
                break;
            }
        }

        // 1. Scan Zone
        if (Config.ShowScanZone && _scanRegion.Width > 0)
        {
            DrawScanZone(dc, _scanRegion);
        }

        // 2. Crosshair
        if (Config.ShowCrosshair)
        {
            DrawCrosshair(dc, cx, cy, isOnTarget, isHeadLocked);
        }

        // 3. Snaplines
        if (Config.ShowSnaplines && _targets.Count > 0)
        {
            DrawSnaplines(dc, _targets, cx, cy, screenH);
        }

        // 4. Target Boxes & Headshot Reticles
        foreach (var t in _targets)
        {
            DrawTarget(dc, t, cx, cy);
        }

        // 5. HUD Stats
        if (Config.ShowHudStats)
        {
            DrawHudStats(dc, _fps, _latencyMs, _targets.Count, _modelName);
        }
    }

    private void DrawScanZone(DrawingContext dc, Rect reg)
    {
        var pen = new Pen(new SolidColorBrush(Color.FromArgb(45, 0, 255, 204)), 1);
        pen.DashStyle = DashStyles.Dash;
        dc.DrawRectangle(null, pen, reg);

        // Corner accents
        var accentPen = new Pen(new SolidColorBrush(Color.FromArgb(140, 0, 255, 204)), 2);
        double cl = 16;
        double x = reg.X, y = reg.Y, w = reg.Width, h = reg.Height;

        dc.DrawLine(accentPen, new Point(x, y), new Point(x + cl, y));
        dc.DrawLine(accentPen, new Point(x, y), new Point(x, y + cl));
        dc.DrawLine(accentPen, new Point(x + w, y), new Point(x + w - cl, y));
        dc.DrawLine(accentPen, new Point(x + w, y), new Point(x + w, y + cl));
        dc.DrawLine(accentPen, new Point(x, y + h), new Point(x + cl, y + h));
        dc.DrawLine(accentPen, new Point(x, y + h), new Point(x, y + h - cl));
        dc.DrawLine(accentPen, new Point(x + w, y + h), new Point(x + w - cl, y + h));
        dc.DrawLine(accentPen, new Point(x + w, y + h), new Point(x + w, y + h - cl));
    }

    private void DrawCrosshair(DrawingContext dc, double cx, double cy, bool onTarget, bool headLocked)
    {
        Color c;
        double size;
        if (headLocked)
        {
            c = Color.FromRgb(255, 0, 85); // Crimson
            size = 6;
        }
        else if (onTarget)
        {
            c = (Color)ColorConverter.ConvertFromString(Config.ClosestColor);
            size = 5.5;
        }
        else
        {
            c = Color.FromRgb(0, 255, 204); // Cyan
            size = 4;
        }

        // Glow ring
        var glowBrush = new SolidColorBrush(Color.FromArgb((byte)(headLocked ? 130 : (onTarget ? 100 : 65)), c.R, c.G, c.B));
        dc.DrawEllipse(glowBrush, null, new Point(cx, cy), size * 2.4, size * 2.4);

        // Center dot
        dc.DrawEllipse(new SolidColorBrush(c), null, new Point(cx, cy), size / 2.0, size / 2.0);

        // Active lock reticle
        if (onTarget || headLocked)
        {
            var reticlePen = new Pen(new SolidColorBrush(c), headLocked ? 2 : 1.5);
            double r = size * (headLocked ? 3.5 : 3.2);
            dc.DrawEllipse(null, reticlePen, new Point(cx, cy), r, r);

            // 4 lock ticks
            double tick = headLocked ? 5 : 4;
            dc.DrawLine(reticlePen, new Point(cx, cy - r - tick), new Point(cx, cy - r + 1));
            dc.DrawLine(reticlePen, new Point(cx, cy + r - 1), new Point(cx, cy + r + tick));
            dc.DrawLine(reticlePen, new Point(cx - r - tick, cy), new Point(cx - r + 1, cy));
            dc.DrawLine(reticlePen, new Point(cx + r - 1, cy), new Point(cx + r + tick, cy));

            // Status label
            string label = headLocked ? "[CRITICAL HEAD LOCK]" : "[TARGET ACQUIRED]";
            var ft = new FormattedText(label, CultureInfo.InvariantCulture, FlowDirection.LeftToRight, _consolasBold, 10, new SolidColorBrush(c), 1.0);
            dc.DrawText(ft, new Point(cx - ft.Width / 2, cy + r + 4));
        }
    }

    private void DrawSnaplines(DrawingContext dc, List<DetectedTarget> targets, double cx, double cy, double screenH)
    {
        double ox = cx;
        double oy = Config.SnaplineOrigin == "bottom" ? screenH : cy;

        foreach (var t in targets)
        {
            if (t.IsClosest)
            {
                var c = (Color)ColorConverter.ConvertFromString(Config.ClosestColor);
                var pen = new Pen(new SolidColorBrush(Color.FromArgb(210, c.R, c.G, c.B)), 1.8);
                dc.DrawLine(pen, new Point(ox, oy), new Point(t.Cx, t.Y2));
                break;
            }
        }
    }

    private void DrawTarget(DrawingContext dc, DetectedTarget t, double screenCx, double screenCy)
    {
        Color baseCol;
        if (t.IsGhost)
        {
            baseCol = Color.FromArgb((byte)(220 * t.GhostAlpha), 179, 136, 255);
        }
        else if (t.IsClosest)
        {
            baseCol = (Color)ColorConverter.ConvertFromString(Config.ClosestColor);
        }
        else
        {
            baseCol = (Color)ColorConverter.ConvertFromString(Config.EnemyColor);
        }

        var borderBrush = new SolidColorBrush(baseCol);
        var fillBrush = new SolidColorBrush(Color.FromArgb((byte)(t.IsGhost ? 15 : (t.IsClosest ? 35 : 20)), baseCol.R, baseCol.G, baseCol.B));
        var boxPen = new Pen(borderBrush, Config.BoxThickness);
        if (t.IsGhost) boxPen.DashStyle = DashStyles.Dash;

        // Subtle fill
        dc.DrawRectangle(fillBrush, null, new Rect(t.X1, t.Y1, t.Width, t.Height));

        // Draw Box or Corners
        if (Config.BoxStyle == "corners")
        {
            double cl = Math.Min(14, Math.Min(t.Width / 3.0, t.Height / 3.0));
            double x1 = t.X1, y1 = t.Y1, x2 = t.X2, y2 = t.Y2;

            dc.DrawLine(boxPen, new Point(x1, y1), new Point(x1 + cl, y1));
            dc.DrawLine(boxPen, new Point(x1, y1), new Point(x1, y1 + cl));
            dc.DrawLine(boxPen, new Point(x2, y1), new Point(x2 - cl, y1));
            dc.DrawLine(boxPen, new Point(x2, y1), new Point(x2, y1 + cl));
            dc.DrawLine(boxPen, new Point(x1, y2), new Point(x1 + cl, y2));
            dc.DrawLine(boxPen, new Point(x1, y2), new Point(x1, y2 - cl));
            dc.DrawLine(boxPen, new Point(x2, y2), new Point(x2 - cl, y2));
            dc.DrawLine(boxPen, new Point(x2, y2), new Point(x2, y2 - cl));
        }
        else
        {
            dc.DrawRectangle(null, boxPen, new Rect(t.X1, t.Y1, t.Width, t.Height));
        }

        // Target badge
        if (Config.ShowLabels)
        {
            string badgeText = t.IsGhost ? $"👻 GHOST {t.ClassName} [{t.DtLoss:F1}s]" : t.ClassName;
            if (Config.ShowConfidence && !t.IsGhost) badgeText += $" {(int)(t.Confidence * 100)}%";
            if (Config.ShowDistance && !t.IsGhost) badgeText += $" [{(int)t.DistToCrosshair}px]";

            var ft = new FormattedText(badgeText, CultureInfo.InvariantCulture, FlowDirection.LeftToRight, _consolasBold, 10, Brushes.White, 1.0);
            double pad = 3;
            double bgW = ft.Width + pad * 4;
            double bgH = ft.Height + pad * 2;
            double bgX = t.X1;
            double bgY = t.Y1 - bgH - 2;
            if (bgY < 10) bgY = t.Y1 + 2;

            dc.DrawRoundedRectangle(new SolidColorBrush(Color.FromArgb(220, 12, 14, 18)), new Pen(borderBrush, 1), new Rect(bgX, bgY, bgW, bgH), 3, 3);
            dc.DrawText(ft, new Point(bgX + pad * 2, bgY + pad));
        }

        // 6. Precision Headshot Marker (Golden Diamond Reticle)
        if (Config.ShowHeadMarker && !t.IsGhost)
        {
            double hx = t.HeadCx;
            double hy = t.HeadCy;
            double rx = Math.Max(4, t.HeadW / 2.0);
            double ry = Math.Max(4, t.HeadH / 2.0);

            Color headCol;
            double lineW;
            if (t.IsHeadLocked)
            {
                headCol = Color.FromRgb(255, 0, 85);
                rx *= 1.15;
                ry *= 1.15;
                lineW = 2.0;
            }
            else
            {
                headCol = (Color)ColorConverter.ConvertFromString(Config.HeadMarkerColor);
                lineW = 1.5;
            }

            var headBrush = new SolidColorBrush(headCol);
            var headFill = new SolidColorBrush(Color.FromArgb((byte)(t.IsHeadLocked ? 65 : 25), headCol.R, headCol.G, headCol.B));
            var headPen = new Pen(headBrush, lineW);

            // Diamond Geometry
            var streamGeom = new StreamGeometry();
            using (var ctx = streamGeom.Open())
            {
                ctx.BeginFigure(new Point(hx, hy - ry), true, true);
                ctx.LineTo(new Point(hx + rx, hy), true, false);
                ctx.LineTo(new Point(hx, hy + ry), true, false);
                ctx.LineTo(new Point(hx - rx, hy), true, false);
            }
            streamGeom.Freeze();
            dc.DrawGeometry(headFill, headPen, streamGeom);

            // Precision center pip
            dc.DrawEllipse(headBrush, null, new Point(hx, hy), 1.8, 1.8);

            // Stance tag
            if (t.Stance == "CROUCH")
            {
                var ftCrouch = new FormattedText("CROUCH", CultureInfo.InvariantCulture, FlowDirection.LeftToRight, _consolasBold, 8, new SolidColorBrush(Color.FromArgb(190, 255, 170, 0)), 1.0);
                dc.DrawText(ftCrouch, new Point(hx + rx + 3, hy - 5));
            }

            // Cross-ticks on lock
            if (t.IsHeadLocked)
            {
                double tick = 4;
                dc.DrawLine(headPen, new Point(hx, hy - ry - tick), new Point(hx, hy - ry));
                dc.DrawLine(headPen, new Point(hx, hy + ry), new Point(hx, hy + ry + tick));
                dc.DrawLine(headPen, new Point(hx - rx - tick, hy), new Point(hx - rx, hy));
                dc.DrawLine(headPen, new Point(hx + rx, hy), new Point(hx + rx + tick, hy));
            }
        }
    }

    private void DrawHudStats(DrawingContext dc, float fps, float latencyMs, int targetCount, string modelName)
    {
        string text = $"⚡ C# DIRECTML | {fps:F0} FPS | {latencyMs:F1}ms | THREATS: {targetCount} | {modelName}";
        var ft = new FormattedText(text, CultureInfo.InvariantCulture, FlowDirection.LeftToRight, _consolasBold, 11, Brushes.Cyan, 1.0);

        double pad = 6;
        double w = ft.Width + pad * 2;
        double h = ft.Height + pad * 2;
        dc.DrawRoundedRectangle(new SolidColorBrush(Color.FromArgb(200, 10, 12, 16)), new Pen(new SolidColorBrush(Color.FromArgb(100, 0, 255, 204)), 1), new Rect(14, 14, w, h), 4, 4);
        dc.DrawText(ft, new Point(14 + pad, 14 + pad));
    }
}
