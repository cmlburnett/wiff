import wiff

import datetime
import unittest
import tempfile
import os
import random
import struct

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
				w = wiff.WIFF.new(fname, props, force=False)
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

				self.assertEqual(w.files[0].fidx_start.val, 0)
				self.assertEqual(w.files[0].fidx_end.val, 0)
				self.assertEqual(w.files[0].name.val, fname)

				w.close()


				# Compare binary data
				expected_dat = 'WIFFINFO'.encode('ascii')
				expected_dat += struct.pack("<QQ", 4096, 1)
				# WIFFINFO header
				expected_dat += struct.pack("<HHHHHHIHHQQ", 36, 58, 80, 91, 147, 201, 12345, 2, 1, 0, 0)
				expected_dat += "20010203 040506.070809".encode('ascii')
				expected_dat += "20101112 131415.161718".encode('ascii')
				expected_dat += "hello world".encode('ascii')
				# Channel jumptable
				expected_dat += struct.pack('<HHHH', 8,32, 32,56)
				# Channel 0
				expected_dat += struct.pack('<BHBHHH', 0, 10, 12, 11, 13, 24)
				expected_dat += "IuVlead test I".encode('ascii')
				# Channel 1
				expected_dat += struct.pack('<BHBHHH', 1, 10, 12, 11, 13, 24)
				expected_dat += "XmAlead test X".encode('ascii')
				# File jumptable
				expected_dat += struct.pack('<HH', 12,54)
				# File 0
				expected_dat += struct.pack('<HHHH', 0,0,0,0)
				expected_dat += struct.pack('<BHHQQ', 0, 21, 21+len(fname), 0,0)
				expected_dat += fname.encode('ascii')

				# Make HEX (easier to view diff strings than binary)
				expected_dat = expected_dat.hex()

				with open(fname, 'rb') as g:
					dat = g.read()
				self.maxDiff = None
				self.assertEqual(len(dat), 4096)
				# Compare non-zero data
				self.assertEqual(dat.hex()[0:len(expected_dat)], expected_dat)
				# Compare zero data to make sure remainder of binary data is actually zero
				self.assertEqual(dat.hex()[len(expected_dat):], '0'*(8192-len(expected_dat)))
			finally:
				os.unlink(fname)

	def test_multifile(self):
		with tempfile.NamedTemporaryFile() as f:
			fname1 = f.name + '.wiff'
			fname2 = f.name + '-2.wiff'
			try:
				random.seed(0)

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
				w = wiff.WIFF.new(fname1, props, force=False)
				w.set_file(fname1)
				w.new_segment([0,1], segmentid=1)

				for i in range(10):
					w.add_frame(struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12)))

				w.new_file(fname2)
				w.new_segment([0,1], segmentid=2)

				for i in range(10):
					w.add_frame(struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12)))


				self.assertTrue(os.path.exists(fname1))
				self.assertTrue(os.path.exists(fname2))

				self.assertEqual(w.start, s_date)
				self.assertEqual(w.end, e_date)
				self.assertEqual(w.description, "hello world")
				self.assertEqual(w.fs, 12345)
				self.assertEqual(w.num_channels, 2)
				self.assertEqual(w.num_files, 2)
				self.assertEqual(w.num_frames, 20)
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

				self.assertEqual(w.files[0].fidx_start.val, 0)
				self.assertEqual(w.files[0].fidx_end.val, 10)
				self.assertEqual(w.files[0].name.val, fname1)

				self.assertEqual(w.files[1].fidx_start.val, 10)
				self.assertEqual(w.files[1].fidx_end.val, 20)
				self.assertEqual(w.files[1].name.val, fname2)


				expected_dat = 'WIFFINFO'.encode('ascii')
				expected_dat += struct.pack("<QQ", 4096, 1)
				# WIFFINFO header
				expected_dat += struct.pack("<HHHHHHIHHQQ", 36, 58, 80, 91, 147, 245, 12345, 2, 2, 20, 0)
				expected_dat += "20010203 040506.070809".encode('ascii')
				expected_dat += "20101112 131415.161718".encode('ascii')
				expected_dat += "hello world".encode('ascii')
				# Channel jumptable
				expected_dat += struct.pack('<HHHH', 8,32, 32,56)
				# Channel 0
				expected_dat += struct.pack('<BHBHHH', 0, 10, 12, 11, 13, 24)
				expected_dat += "IuVlead test I".encode('ascii')
				# Channel 1
				expected_dat += struct.pack('<BHBHHH', 1, 10, 12, 11, 13, 24)
				expected_dat += "XmAlead test X".encode('ascii')
				# File jumptable
				expected_dat += struct.pack('<HHHH', 12,54, 54,98)
				expected_dat += struct.pack('<HH', 0,0)
				# File 0
				expected_dat += struct.pack('<BHHQQ', 0, 21, 21+len(fname1), 0,10)
				expected_dat += fname1.encode('ascii')
				# File 1
				expected_dat += struct.pack('<BHHQQ', 1, 21, 21+len(fname2), 10,20)
				expected_dat += fname2.encode('ascii')
				# Make HEX (easier to view diff strings than binary)
				expected_dat = expected_dat.hex()


				with open(fname1, 'rb') as g:
					dat = g.read()
				self.maxDiff = None
				self.assertEqual(len(dat), 8192)
				# Compare non-zero data
				self.assertEqual(dat.hex()[0:len(expected_dat)], expected_dat)
				# Compare zero data to make sure remainder of binary data is actually zero
				self.assertEqual(dat.hex()[len(expected_dat):4096], '0'*(4096-len(expected_dat)))



			finally:
				os.unlink(fname1)
				os.unlink(fname2)

