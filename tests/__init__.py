import wiff

import datetime
import unittest
import tempfile
import os

class SimpleTests(unittest.TestCase):
	def test_infoheader(self):
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				s_date = "20010203 040506.070809"
				e_date = "20101112 131415.161718"
				props = {
					'start': datetime.datetime.strptime(s_date, "%Y%m%d %H%M%S.%f"),
					'end':   datetime.datetime.strptime(e_date, "%Y%m%d %H%M%S.%f"),
					'description': "hello world",
					'fs': 12345,
					'channels': [
						{'name': 'I', 'bit': 12, 'unit': 'uV', 'comment': 'lead test I'},
						{'name': 'X', 'bit': 12, 'unit': 'mA', 'comment': 'lead test X'},
					],
					'files': [],
				}
				w = wiff.WIFF(fname, props)
				self.assertEqual(w.start, s_date)
				self.assertEqual(w.end, e_date)
				self.assertEqual(w.description, "hello world")
				self.assertEqual(w.fs, 12345)
				self.assertEqual(w.num_channels, 2)
				self.assertEqual(w.num_files, 1)
				self.assertEqual(w.num_frames, 0)
				self.assertEqual(w.num_annotations, 0)

				self.assertEqual(w._chunks['INFO'].chunk.offset, 0)
				self.assertEqual(w._chunks['INFO'].chunk.magic, "WIFFINFO")
				self.assertEqual(w._chunks['INFO'].chunk.size, 4096)

				self.assertEqual(w._chunks['INFO'].offset, 24)

				self.assertEqual(w.channels[0].name.val, "I")
				self.assertEqual(w.channels[0].unit.val, "uV")
				self.assertEqual(w.channels[0].bit.val, 12)
				self.assertEqual(w.channels[0].comment.val, "lead test I")

				self.assertEqual(w.channels[1].name.val, "X")
				self.assertEqual(w.channels[1].unit.val, "mA")
				self.assertEqual(w.channels[1].bit.val, 12)
				self.assertEqual(w.channels[1].comment.val, "lead test X")

				w.close()


				# Compare binary data

				expected_dat = b'WIFFINFO\x00\x10\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00$\x00:\x00P\x00[\x00\x93\x00\xc1\x0090\x00\x00\x02\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0020010203 040506.07080920101112 131415.161718hello world\x08\x00 \x00 \x008\x00\x00\n\x00\x0c\x0b\x00\r\x00\x18\x00IuVlead test I\x01\n\x00\x0c\x0b\x00\r\x00\x18\x00XmAlead test X\x04\x00.\x00\x00\x15\x00*\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' + fname.encode('ascii')
				# Pad with zeros to a full page
				expected_dat += b'\0' * (4096-len(expected_dat))

				with open(fname, 'rb') as g:
					dat = g.read()
				self.assertEqual(len(dat), 4096)
				# Verify binary of the chunk header
				self.assertEqual(dat[0:24], expected_dat[0:24])
				# Verify binary of the chunk data
				self.assertEqual(dat, expected_dat)

			finally:
				os.unlink(fname)



