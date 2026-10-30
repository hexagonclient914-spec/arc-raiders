using System;
using System.IO;

namespace YoloTacticalVisionCS;

public static class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        string logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "startup.log");
        File.WriteAllText(logPath, $"[INFO] Program.Main started at {DateTime.Now}\n");

        try
        {
            var app = new App();
            File.AppendAllText(logPath, "[INFO] App instance created\n");
            app.Run();
            File.AppendAllText(logPath, "[INFO] App.Run finished cleanly\n");
        }
        catch (Exception ex)
        {
            File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "fatal_startup.log"), ex.ToString());
        }
    }
}
