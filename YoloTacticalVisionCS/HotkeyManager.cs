using System;
using System.Runtime.InteropServices;
using System.Windows.Interop;

namespace YoloTacticalVisionCS;

public class HotkeyManager : IDisposable
{
    [DllImport("user32.dll")]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    private const int WM_HOTKEY = 0x0312;
    private const uint VK_F7 = 0x76;
    private const uint VK_F8 = 0x77;

    public const int HOTKEY_F7_ID = 9001;
    public const int HOTKEY_F8_ID = 9002;

    private readonly IntPtr _hwnd;
    private readonly ThreadMessageFilter _filter;

    public event Action? OnF7Pressed;
    public event Action? OnF8Pressed;

    public HotkeyManager(IntPtr hwnd)
    {
        _hwnd = hwnd;
        _filter = new ThreadMessageFilter(this);
        ComponentDispatcher.ThreadFilterMessage += _filter.FilterMessage;

        RegisterHotKey(_hwnd, HOTKEY_F7_ID, 0, VK_F7);
        RegisterHotKey(_hwnd, HOTKEY_F8_ID, 0, VK_F8);
    }

    private class ThreadMessageFilter
    {
        private readonly HotkeyManager _parent;
        public ThreadMessageFilter(HotkeyManager parent) => _parent = parent;

        public void FilterMessage(ref MSG msg, ref bool handled)
        {
            if (msg.message == WM_HOTKEY)
            {
                int id = msg.wParam.ToInt32();
                if (id == HOTKEY_F7_ID)
                {
                    _parent.OnF7Pressed?.Invoke();
                    handled = true;
                }
                else if (id == HOTKEY_F8_ID)
                {
                    _parent.OnF8Pressed?.Invoke();
                    handled = true;
                }
            }
        }
    }

    public void Dispose()
    {
        UnregisterHotKey(_hwnd, HOTKEY_F7_ID);
        UnregisterHotKey(_hwnd, HOTKEY_F8_ID);
        ComponentDispatcher.ThreadFilterMessage -= _filter.FilterMessage;
    }
}
