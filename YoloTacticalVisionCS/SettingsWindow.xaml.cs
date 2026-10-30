using System;
using System.IO;
using System.Windows;
using System.Windows.Media;

namespace YoloTacticalVisionCS;

public partial class SettingsWindow : Window
{
    private readonly YoloConfig _config;
    private readonly YoloInferenceEngine _engine;
    private readonly OverlayWindow _overlay;
    private bool _isInitializing = true;

    public SettingsWindow(YoloConfig config, YoloInferenceEngine engine, OverlayWindow overlay)
    {
        InitializeComponent();
        _config = config;
        _engine = engine;
        _overlay = overlay;

        RefreshModelList();
        LoadConfigToUi();
        _isInitializing = false;

        Closing += (s, e) =>
        {
            e.Cancel = true;
            Hide();
        };
    }

    public void UpdateMetrics(float fps, float latencyMs, int threatCount)
    {
        Dispatcher.InvokeAsync(() =>
        {
            TxtHardware.Text = $"Hardware: NVIDIA RTX 4060 (DirectML GPU) | {fps:F0} FPS | {latencyMs:F1}ms | Threats: {threatCount}";
        });
    }

    private void RefreshModelList()
    {
        CmbModel.Items.Clear();
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;

        // Search directory for .onnx files
        var files = Directory.GetFiles(baseDir, "*.onnx");
        if (files.Length == 0)
        {
            string parentDir = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", ".."));
            if (Directory.Exists(parentDir))
            {
                files = Directory.GetFiles(parentDir, "*.onnx");
            }
        }

        foreach (var f in files)
        {
            CmbModel.Items.Add(Path.GetFileName(f));
        }

        string curModel = Path.GetFileName(_config.ModelPath);
        if (CmbModel.Items.Contains(curModel))
        {
            CmbModel.SelectedItem = curModel;
        }
        else if (CmbModel.Items.Count > 0)
        {
            CmbModel.SelectedIndex = 0;
        }
    }

    private void LoadConfigToUi()
    {
        CmbRegion.SelectedIndex = _config.ScanRegionMode switch
        {
            "center_480" => 0,
            "center_640" => 1,
            _ => 2
        };

        SldConf.Value = (int)(_config.ConfidenceThreshold * 100);
        LblConf.Text = $"Confidence Threshold: {(int)SldConf.Value}%";

        ChkHeadMarker.IsChecked = _config.ShowHeadMarker;
        ChkStance.IsChecked = _config.StanceDetection;
        ChkLatComp.IsChecked = _config.LatencyCompensation;
        ChkClosest.IsChecked = _config.ShowClosestIndicator;
        ChkZone.IsChecked = _config.ShowScanZone;

        ChkSmoothing.IsChecked = _config.BoxSmoothing;
        ChkAdaptive.IsChecked = _config.AdaptiveSmoothing;
        ChkCrosshair.IsChecked = _config.ShowCrosshair;
        ChkSnaplines.IsChecked = _config.ShowSnaplines;
        ChkStats.IsChecked = _config.ShowHudStats;

        HighlightProfileButton(_config.ActiveGameProfile);
    }

    private void HighlightProfileButton(string profile)
    {
        BtnProfVal.BorderThickness = new Thickness(profile == "valorant" ? 2 : 1);
        BtnProfCs2.BorderThickness = new Thickness(profile == "cs2" ? 2 : 1);
        BtnProfArc.BorderThickness = new Thickness(profile == "arc_raiders" ? 2 : 1);

        if (profile == "valorant") BtnProfVal.BorderBrush = new SolidColorBrush(Color.FromRgb(0, 255, 204));
        else BtnProfVal.BorderBrush = new SolidColorBrush(Color.FromRgb(255, 70, 85));

        if (profile == "cs2") BtnProfCs2.BorderBrush = new SolidColorBrush(Color.FromRgb(0, 255, 204));
        else BtnProfCs2.BorderBrush = new SolidColorBrush(Color.FromRgb(229, 169, 60));

        if (profile == "arc_raiders") BtnProfArc.BorderBrush = new SolidColorBrush(Color.FromRgb(0, 255, 204));
        else BtnProfArc.BorderBrush = new SolidColorBrush(Color.FromRgb(0, 255, 204));
    }

    public void ApplyGameProfile(string profile)
    {
        _config.ActiveGameProfile = profile;

        if (profile == "valorant")
        {
            _config.ModelPath = "valorant_30k_640.onnx";
            _config.ScanRegionMode = "center_480";
            _config.ConfidenceThreshold = 0.50f;
            _config.EnemyColor = "#FF2A55";
            _config.ClosestColor = "#FFE600";
            _config.BoxStyle = "box";
        }
        else if (profile == "cs2")
        {
            _config.ModelPath = "GGMCS2.onnx";
            _config.ScanRegionMode = "center_640";
            _config.ConfidenceThreshold = 0.45f;
            _config.EnemyColor = "#FF3355";
            _config.ClosestColor = "#00FFCC";
            _config.BoxStyle = "corners";
        }
        else if (profile == "arc_raiders")
        {
            _config.ModelPath = "arc_raiders_yolo11_better.onnx";
            _config.ScanRegionMode = "center_640";
            _config.ConfidenceThreshold = 0.38f;
            _config.EnemyColor = "#FF3355";
            _config.ClosestColor = "#00FFCC";
            _config.BoxStyle = "corners";
        }

        _config.ShowHeadMarker = true;
        _config.StanceDetection = true;
        _config.LatencyCompensation = true;
        _config.BoxSmoothing = true;
        _config.AdaptiveSmoothing = true;
        _config.Save();

        LoadConfigToUi();
        _engine.LoadModel(_config.ModelPath);
    }

    private void BtnProfVal_Click(object sender, RoutedEventArgs e) => ApplyGameProfile("valorant");
    private void BtnProfCs2_Click(object sender, RoutedEventArgs e) => ApplyGameProfile("cs2");
    private void BtnProfArc_Click(object sender, RoutedEventArgs e) => ApplyGameProfile("arc_raiders");

    private void CmbModel_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
    {
        if (_isInitializing) return;
        if (CmbModel.SelectedItem is string modelName && !string.IsNullOrEmpty(modelName))
        {
            _config.ModelPath = modelName;
            _config.Save();
            _engine.LoadModel(modelName);
        }
    }

    private void CmbRegion_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
    {
        if (_isInitializing) return;
        _config.ScanRegionMode = CmbRegion.SelectedIndex switch
        {
            0 => "center_480",
            1 => "center_640",
            _ => "fullscreen"
        };
        _config.Save();
    }

    private void SldConf_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (_isInitializing || LblConf == null) return;
        int val = (int)SldConf.Value;
        LblConf.Text = $"Confidence Threshold: {val}%";
        _config.ConfidenceThreshold = val / 100f;
        _config.Save();
    }

    private void OnVisualChanged(object sender, RoutedEventArgs e)
    {
        _config.ShowHeadMarker = ChkHeadMarker.IsChecked == true;
        _config.StanceDetection = ChkStance.IsChecked == true;
        _config.LatencyCompensation = ChkLatComp.IsChecked == true;
        _config.ShowClosestIndicator = ChkClosest.IsChecked == true;
        _config.ShowScanZone = ChkZone.IsChecked == true;

        _config.BoxSmoothing = ChkSmoothing.IsChecked == true;
        _config.AdaptiveSmoothing = ChkAdaptive.IsChecked == true;
        _config.ShowCrosshair = ChkCrosshair.IsChecked == true;
        _config.ShowSnaplines = ChkSnaplines.IsChecked == true;
        _config.ShowHudStats = ChkStats.IsChecked == true;

        _config.Save();
    }

    private void BtnToggleOverlay_Click(object sender, RoutedEventArgs e)
    {
        if (_overlay.Visibility == Visibility.Visible)
            _overlay.Hide();
        else
            _overlay.Show();
    }

    private void BtnReset_Click(object sender, RoutedEventArgs e)
    {
        var def = new YoloConfig();
        ApplyGameProfile(def.ActiveGameProfile);
    }
}
