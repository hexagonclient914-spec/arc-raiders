using System;

namespace YoloTacticalVisionCS;

public class DetectedTarget
{
    public int TargetId { get; set; }
    public float X1 { get; set; }
    public float Y1 { get; set; }
    public float X2 { get; set; }
    public float Y2 { get; set; }
    public float Cx { get; set; }
    public float Cy { get; set; }
    public float Width { get; set; }
    public float Height { get; set; }
    public int ClassId { get; set; }
    public string ClassName { get; set; } = "TARGET";
    public float Confidence { get; set; }

    // Velocity & tracking
    public float Vx { get; set; }
    public float Vy { get; set; }
    public double LastSeen { get; set; }
    public double LastUpdate { get; set; }
    public bool IsGhost { get; set; }
    public float GhostAlpha { get; set; } = 1.0f;
    public double DtLoss { get; set; }

    // Distance to center crosshair
    public float DistToCrosshair { get; set; }
    public bool IsClosest { get; set; }

    // Stance & Headshot Precision
    public string Stance { get; set; } = "STAND"; // STAND, CROUCH, NORMAL
    public float HeadRatio { get; set; } = 0.16f;
    public float HeadCx { get; set; }
    public float HeadCy { get; set; }
    public float HeadW { get; set; }
    public float HeadH { get; set; }
    public float DistHead { get; set; }
    public bool IsHeadLocked { get; set; }
}
