"""Regression for stale frames resetting the GIF palette/filter pipeline."""
from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

from pv_frd_animation.encoding import encode, bounded_frames


def write_png(path, width, height, color):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    pixels = (b'\0' + bytes(color)*width)*height
    path.write_bytes(b'\x89PNG\r\n\x1a\n' +
                     chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0)) +
                     chunk(b'IDAT',zlib.compress(pixels)) + chunk(b'IEND',b''))


class EncodingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is needed for the export regression')
    def test_gif_ignores_stale_frames_with_a_different_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            frames = out/'frames'
            frames.mkdir()
            colors = [(255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255)]
            for index,color in enumerate(colors):
                width,height = (64,32) if index < 3 else (16,8)
                write_png(frames/('frame_%05d.png' % index),width,height,color)
            (out/'settings.json').write_text(json.dumps(dict(frame_count=3)))
            a = Namespace(output=str(out),ffmpeg=shutil.which('ffmpeg'),fps=5,
                          crf=14,preset='slow',gif_fps=5,gif_width=64,gif_colors=256)
            with contextlib.redirect_stdout(io.StringIO()):
                encode(a)
            raw = subprocess.run([a.ffmpeg,'-v','error','-i',str(out/'beam_animation.gif'),
                                  '-vsync','0','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],
                                 stdout=subprocess.PIPE,check=True).stdout
            frame_bytes = 64*32*3
            self.assertEqual(len(raw),3*frame_bytes)
            for index,color in enumerate(colors[:3]):
                self.assertEqual(raw[index*frame_bytes:(index+1)*frame_bytes],bytes(color)*(64*32))
            self.assertFalse(list(out.glob('.encode-*')))
            self.assertTrue((frames/'frame_00004.png').exists())

    def test_missing_active_frame_cleans_up_and_leaves_existing_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out/'frames').mkdir()
            write_png(out/'frames/frame_00000.png',4,4,(255,0,0))
            export = out/'beam_animation.gif'
            export.write_bytes(b'existing export')
            with self.assertRaises(FileNotFoundError):
                with bounded_frames(out,2):
                    self.fail('An incomplete input sequence must not be encoded')
            self.assertEqual(export.read_bytes(),b'existing export')
            self.assertFalse(list(out.glob('.encode-*')))


if __name__ == '__main__':
    unittest.main()
