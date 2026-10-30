using System;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace YoloTacticalVisionCS;

public class YoloConfig
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = true;

    [JsonPropertyName("model_path")]
    public string ModelPath { get; set; } = "valorant_30k_640.onnx";

    [JsonPropertyName("confidence_threshold")]
    public float ConfidenceThreshold { get; set; } = 0.50f;

    [JsonPropertyName("iou_threshold")]
    public float IouThreshold { get; set; } = 0.45f;

    [JsonPropertyName("scan_region_mode")]
    public string ScanRegionMode { get; set; } = "center_480";

    [JsonPropertyName("max_fps")]
    public int MaxFps { get; set; } = 144;

    [JsonPropertyName("box_style")]
    public string BoxStyle { get; set; } = "box";

    [JsonPropertyName("box_thickness")]
    public int BoxThickness { get; set; } = 2;

    [JsonPropertyName("enemy_color")]
    public string EnemyColor { get; set; } = "#FF2A55";

    [JsonPropertyName("closest_color")]
    public string ClosestColor { get; set; } = "#FFE600";

    [JsonPropertyName("head_marker_color")]
    public string HeadMarkerColor { get; set; } = "#FFE600";

    [JsonPropertyName("show_labels")]
    public bool ShowLabels { get; set; } = true;

    [JsonPropertyName("show_confidence")]
    public bool ShowConfidence { get; set; } = true;

    [JsonPropertyName("show_distance")]
    public bool ShowDistance { get; set; } = true;

    [JsonPropertyName("show_snaplines")]
    public bool ShowSnaplines { get; set; } = true;

    [JsonPropertyName("snapline_origin")]
    public string SnaplineOrigin { get; set; } = "center";

    [JsonPropertyName("show_closest_indicator")]
    public bool ShowClosestIndicator { get; set; } = true;

    [JsonPropertyName("show_scan_zone")]
    public bool ShowScanZone { get; set; } = true;

    [JsonPropertyName("show_hud_stats")]
    public bool ShowHudStats { get; set; } = true;

    [JsonPropertyName("show_crosshair")]
    public bool ShowCrosshair { get; set; } = true;

    [JsonPropertyName("on_target_crosshair")]
    public bool OnTargetCrosshair { get; set; } = true;

    [JsonPropertyName("show_head_marker")]
    public bool ShowHeadMarker { get; set; } = true;

    [JsonPropertyName("box_smoothing")]
    public bool BoxSmoothing { get; set; } = true;

    [JsonPropertyName("box_smoothing_factor")]
    public float BoxSmoothingFactor { get; set; } = 0.65f;

    [JsonPropertyName("adaptive_smoothing")]
    public bool AdaptiveSmoothing { get; set; } = true;

    [JsonPropertyName("stance_detection")]
    public bool StanceDetection { get; set; } = true;

    [JsonPropertyName("latency_compensation")]
    public bool LatencyCompensation { get; set; } = true;

    [JsonPropertyName("active_game_profile")]
    public string ActiveGameProfile { get; set; } = "valorant";

    private static readonly string ConfigPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "yolo_config.json");

    public static YoloConfig Load()
    {
        try
        {
            if (File.Exists(ConfigPath))
            {
                string json = File.ReadAllText(ConfigPath);
                var cfg = JsonSerializer.Deserialize<YoloConfig>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                if (cfg != null) return cfg;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[Config] Error loading config: {ex.Message}");
        }

        var def = new YoloConfig();
        def.Save();
        return def;
    }

    public void Save()
    {
        try
        {
            var options = new JsonSerializerOptions { WriteIndented = true };
            string json = JsonSerializer.Serialize(this, options);
            File.WriteAllText(ConfigPath, json);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[Config] Error saving config: {ex.Message}");
        }
    }
}
