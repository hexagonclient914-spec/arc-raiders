using System;
using System.Runtime.InteropServices;

namespace YoloTacticalVisionCS;

public class ScreenCapture : IDisposable
{
    [DllImport("user32.dll")]
    private static extern IntPtr GetDC(IntPtr hwnd);

    [DllImport("user32.dll")]
    private static extern int ReleaseDC(IntPtr hwnd, IntPtr hdc);

    [DllImport("gdi32.dll")]
    private static extern IntPtr CreateCompatibleDC(IntPtr hdc);

    [DllImport("gdi32.dll")]
    private static extern bool DeleteDC(IntPtr hdc);

    [DllImport("gdi32.dll")]
    private static extern IntPtr CreateDIBSection(IntPtr hdc, [In] ref BITMAPINFO pbmi, uint pila, out IntPtr ppvBits, IntPtr hSection, uint dwOffset);

    [DllImport("gdi32.dll")]
    private static extern IntPtr SelectObject(IntPtr hdc, IntPtr hgdiobj);

    [DllImport("gdi32.dll")]
    private static extern bool DeleteObject(IntPtr hObject);

    [DllImport("gdi32.dll")]
    private static extern bool BitBlt(IntPtr hdcDest, int nXDest, int nYDest, int nWidth, int nHeight, IntPtr hdcSrc, int nXSrc, int nYSrc, uint dwRop);

    [StructLayout(LayoutKind.Sequential)]
    private struct BITMAPINFOHEADER
    {
        public uint biSize;
        public int biWidth;
        public int biHeight;
        public ushort biPlanes;
        public ushort biBitCount;
        public uint biCompression;
        public uint biSizeImage;
        public int biXPelsPerMeter;
        public int biYPelsPerMeter;
        public uint biClrUsed;
        public uint biClrImportant;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BITMAPINFO
    {
        public BITMAPINFOHEADER bmiHeader;
        public uint bmiColors;
    }

    private const uint SRCCOPY = 0x00CC0020;
    private const uint DIB_RGB_COLORS = 0;

    private IntPtr _hDeskDC;
    private IntPtr _hMemDC;
    private IntPtr _hBitmap;
    private IntPtr _oldBitmap;
    private IntPtr _pBits;
    private int _width;
    private int _height;

    public int Width => _width;
    public int Height => _height;
    public IntPtr BufferPtr => _pBits;

    public ScreenCapture(int width = 640, int height = 640)
    {
        Resize(width, height);
    }

    public void Resize(int width, int height)
    {
        if (_width == width && _height == height && _hMemDC != IntPtr.Zero)
            return;

        Dispose();

        _width = width;
        _height = height;

        _hDeskDC = GetDC(IntPtr.Zero);
        _hMemDC = CreateCompatibleDC(_hDeskDC);

        var bmi = new BITMAPINFO
        {
            bmiHeader = new BITMAPINFOHEADER
            {
                biSize = (uint)Marshal.SizeOf(typeof(BITMAPINFOHEADER)),
                biWidth = width,
                biHeight = -height, // top-down DIB
                biPlanes = 1,
                biBitCount = 32,    // 32-bit BGRA
                biCompression = 0   // BI_RGB
            }
        };

        _hBitmap = CreateDIBSection(_hDeskDC, ref bmi, DIB_RGB_COLORS, out _pBits, IntPtr.Zero, 0);
        _oldBitmap = SelectObject(_hMemDC, _hBitmap);
    }

    public bool Capture(int left, int top, int width, int height)
    {
        if (_hMemDC == IntPtr.Zero || _hDeskDC == IntPtr.Zero)
            return false;

        return BitBlt(_hMemDC, 0, 0, width, height, _hDeskDC, left, top, SRCCOPY);
    }

    public void Dispose()
    {
        if (_hMemDC != IntPtr.Zero)
        {
            if (_oldBitmap != IntPtr.Zero)
            {
                SelectObject(_hMemDC, _oldBitmap);
                _oldBitmap = IntPtr.Zero;
            }
            DeleteDC(_hMemDC);
            _hMemDC = IntPtr.Zero;
        }

        if (_hBitmap != IntPtr.Zero)
        {
            DeleteObject(_hBitmap);
            _hBitmap = IntPtr.Zero;
        }

        if (_hDeskDC != IntPtr.Zero)
        {
            ReleaseDC(IntPtr.Zero, _hDeskDC);
            _hDeskDC = IntPtr.Zero;
        }

        _pBits = IntPtr.Zero;
    }
}
