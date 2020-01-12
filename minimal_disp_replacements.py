import os
import struct

class MinimalMemoryFont(object):
    """
    Replacement for Adafruit_CircuitPython_framebuf.Bitmapfont
    
    Less features but should be a lot faster. Keeps font in memory
    instead of in file.
    """
    def __init__(self, font_name="font5x8.bin"):
        self.font_name = font_name
        try:
            with open(font_name, "rb") as f:
                self.font_width, self.font_height = struct.unpack('BB', f.read(2))
                if 2 + 256 * self.font_width != os.stat(font_name)[6]:
                    raise RuntimeError("Invalid font file: " + font_name)
                self.font_data = []
                while True:
                    d = f.read(1)
                    if not d:
                        break
                    self.font_data.append(struct.unpack('B', d)[0])
        except OSError:
            print("Could not find font file", font_name)
            raise
    
    def draw_char(self, char, x, y, framebuffer, color, size=1): # pylint: disable=too-many-arguments
        """Draw one character at position (x,y) to a framebuffer in a given color"""
        # Go through each column of the character.
        for char_x in range(self.font_width):
            # Grab the byte for the current column of font data.
            line = self.font_data[(ord(char) * self.font_width) + char_x]

            # Go through each row in the column byte.
            for char_y in range(self.font_height):
                # Draw a pixel for each bit that's flipped on.
                if (line >> char_y) & 0x1:
                    framebuffer.pixel(x + char_x, y + char_y, color)
    
    def width(self, text):
        """Return the pixel width of the specified text message."""
        return len(text) * (self.font_width + 1)