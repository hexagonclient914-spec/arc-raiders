using System;
using System.Collections.Generic;

namespace YoloTacticalVisionCS;

public class TargetTracker
{
    private static float Hypot(float dx, float dy) => MathF.Sqrt(dx * dx + dy * dy);

    private readonly Dictionary<int, DetectedTarget> _tracks = new();
    private int _nextId = 1;

    public List<DetectedTarget> Update(
        List<DetectedTarget> detections,
        YoloConfig config,
        float screenCx,
        float screenCy,
        float latencyMs)
    {
        double now = DateTime.UtcNow.Subtract(DateTime.UnixEpoch).TotalSeconds;
        var matchedTrackIds = new HashSet<int>();
        var resultList = new List<DetectedTarget>();

        // 1. Correlate detections with existing tracks
        foreach (var det in detections)
        {
            int bestId = -1;
            float bestDist = float.MaxValue;

            foreach (var kvp in _tracks)
            {
                int tid = kvp.Key;
                if (matchedTrackIds.Contains(tid)) continue;

                var tr = kvp.Value;
                float d = Hypot(det.Cx - tr.Cx, det.Cy - tr.Cy);
                float maxMatchD = MathF.Max(det.Width, MathF.Max(det.Height, 90f));

                if (d < maxMatchD && d < bestDist)
                {
                    bestDist = d;
                    bestId = tid;
                }
            }

            if (bestId != -1)
            {
                var tr = _tracks[bestId];
                float dt = (float)Math.Max(0.001, now - tr.LastSeen);
                float rawVx = (det.Cx - tr.Cx) / dt;
                float rawVy = (det.Cy - tr.Cy) / dt;

                // Clamped velocity low-pass
                float vx = Math.Clamp(0.55f * tr.Vx + 0.45f * rawVx, -2000f, 2000f);
                float vy = Math.Clamp(0.55f * tr.Vy + 0.45f * rawVy, -2000f, 2000f);
                float speed = Hypot(vx, vy);

                // Velocity-Adaptive One-Euro EMA smoothing filter
                if (config.BoxSmoothing)
                {
                    float alpha;
                    if (config.AdaptiveSmoothing)
                    {
                        float speedNorm = Math.Clamp(speed / 500f, 0f, 1f);
                        alpha = 0.28f + 0.60f * speedNorm;
                    }
                    else
                    {
                        alpha = config.BoxSmoothingFactor;
                    }

                    if (bestDist < 120f)
                    {
                        det.X1 = alpha * det.X1 + (1f - alpha) * tr.X1;
                        det.Y1 = alpha * det.Y1 + (1f - alpha) * tr.Y1;
                        det.X2 = alpha * det.X2 + (1f - alpha) * tr.X2;
                        det.Y2 = alpha * det.Y2 + (1f - alpha) * tr.Y2;
                        det.Cx = (det.X1 + det.X2) / 2f;
                        det.Cy = (det.Y1 + det.Y2) / 2f;
                        det.Width = MathF.Max(1f, det.X2 - det.X1);
                        det.Height = MathF.Max(1f, det.Y2 - det.Y1);
                    }
                }

                tr.Cx = det.Cx;
                tr.Cy = det.Cy;
                tr.Width = det.Width;
                tr.Height = det.Height;
                tr.X1 = det.X1;
                tr.Y1 = det.Y1;
                tr.X2 = det.X2;
                tr.Y2 = det.Y2;
                tr.Vx = vx;
                tr.Vy = vy;
                tr.LastSeen = now;
                tr.LastUpdate = now;
                tr.Confidence = det.Confidence;
                tr.ClassId = det.ClassId;
                tr.ClassName = det.ClassName;

                matchedTrackIds.Add(bestId);
                det.TargetId = bestId;
                det.Vx = vx;
                det.Vy = vy;
            }
            else
            {
                int newId = _nextId++;
                var newTrack = new DetectedTarget
                {
                    TargetId = newId,
                    Cx = det.Cx,
                    Cy = det.Cy,
                    Width = det.Width,
                    Height = det.Height,
                    X1 = det.X1,
                    Y1 = det.Y1,
                    X2 = det.X2,
                    Y2 = det.Y2,
                    Vx = 0,
                    Vy = 0,
                    LastSeen = now,
                    LastUpdate = now,
                    Confidence = det.Confidence,
                    ClassId = det.ClassId,
                    ClassName = det.ClassName
                };
                _tracks[newId] = newTrack;
                matchedTrackIds.Add(newId);
                det.TargetId = newId;
            }

            // Stance Detection & Head Position
            float aspect = det.Width / MathF.Max(1f, det.Height);
            float headRatio;
            string stance;

            if (config.StanceDetection)
            {
                if (aspect > 0.48f)
                {
                    headRatio = 0.22f; // Crouching / ducking
                    stance = "CROUCH";
                }
                else if (aspect < 0.32f)
                {
                    headRatio = 0.125f; // Standing tall
                    stance = "STAND";
                }
                else
                {
                    headRatio = 0.155f;
                    stance = "NORMAL";
                }
            }
            else
            {
                headRatio = 0.16f;
                stance = "NORMAL";
            }

            float headX = det.Cx;
            float headY = det.Y1 + det.Height * headRatio;

            // Sub-frame Latency Compensation
            if (config.LatencyCompensation)
            {
                float leadTime = Math.Clamp((latencyMs * 1.25f) / 1000f, 0.004f, 0.040f);
                headX += det.Vx * leadTime;
                headY += det.Vy * leadTime;
            }

            float headH = det.Height * (stance == "STAND" ? 0.16f : 0.20f);
            float headW = MathF.Min(det.Width * 0.44f, headH * 0.90f);

            det.Stance = stance;
            det.HeadRatio = headRatio;
            det.HeadCx = headX;
            det.HeadCy = headY;
            det.HeadW = MathF.Max(5f, headW);
            det.HeadH = MathF.Max(5f, headH);
            det.DistHead = Hypot(headX - screenCx, headY - screenCy);
            det.DistToCrosshair = Hypot(det.Cx - screenCx, det.Cy - screenCy);

            // Anatomical Head Lock check
            float hwRad = MathF.Max(4f, det.HeadW / 2f);
            float hhRad = MathF.Max(4f, det.HeadH / 2f);
            float normSq = MathF.Pow((screenCx - headX) / hwRad, 2f) + MathF.Pow((screenCy - headY) / hhRad, 2f);
            det.IsHeadLocked = normSq <= 1.25f;

            resultList.Add(det);
        }

        // 2. Ghost boxes (cover occlusion tracking)
        var expired = new List<int>();
        foreach (var kvp in _tracks)
        {
            int tid = kvp.Key;
            if (!matchedTrackIds.Contains(tid))
            {
                var tr = kvp.Value;
                double dtLoss = now - tr.LastSeen;
                if (dtLoss < 1.5)
                {
                    float dtStep = (float)(now - tr.LastUpdate);
                    float predCx = tr.Cx + tr.Vx * dtStep;
                    float predCy = tr.Cy + tr.Vy * dtStep;
                    float halfW = tr.Width / 2f;
                    float halfH = tr.Height / 2f;

                    tr.Cx = predCx;
                    tr.Cy = predCy;
                    tr.LastUpdate = now;

                    float ghostAlpha = (float)Math.Clamp(1.0 - (dtLoss / 1.5), 0.2, 1.0);
                    float aspect = tr.Width / MathF.Max(1f, tr.Height);
                    float headRatio = aspect > 0.48f ? 0.22f : (aspect < 0.32f ? 0.125f : 0.155f);
                    float headH = tr.Height * 0.18f;
                    float headW = MathF.Min(tr.Width * 0.44f, headH * 0.90f);

                    var ghost = new DetectedTarget
                    {
                        TargetId = tid,
                        X1 = predCx - halfW,
                        Y1 = predCy - halfH,
                        X2 = predCx + halfW,
                        Y2 = predCy + halfH,
                        Cx = predCx,
                        Cy = predCy,
                        Width = tr.Width,
                        Height = tr.Height,
                        ClassId = tr.ClassId,
                        ClassName = tr.ClassName,
                        Confidence = tr.Confidence,
                        IsGhost = true,
                        GhostAlpha = ghostAlpha,
                        DtLoss = dtLoss,
                        Vx = tr.Vx,
                        Vy = tr.Vy,
                        HeadCx = predCx,
                        HeadCy = (predCy - halfH) + tr.Height * headRatio,
                        HeadW = headW,
                        HeadH = headH,
                        DistToCrosshair = Hypot(predCx - screenCx, predCy - screenCy)
                    };
                    resultList.Add(ghost);
                }
                else
                {
                    expired.Add(tid);
                }
            }
        }

        foreach (var tid in expired)
        {
            _tracks.Remove(tid);
        }

        // Determine closest target
        float closestDist = float.MaxValue;
        int closestIdx = -1;
        for (int i = 0; i < resultList.Count; i++)
        {
            if (resultList[i].DistToCrosshair < closestDist)
            {
                closestDist = resultList[i].DistToCrosshair;
                closestIdx = i;
            }
        }
        if (closestIdx >= 0)
        {
            resultList[closestIdx].IsClosest = true;
        }

        return resultList;
    }
}
