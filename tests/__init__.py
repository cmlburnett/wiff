import wiff

import datetime
import unittest
import tempfile
import os
import random
import struct
import subprocess

class SimpleTests(unittest.TestCase):
	def test_infoheader(self):
		"""
		Simple test to make a WIFFINFO chunk and check that reading via class and binary match.
		"""
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
				self.assertEqual(w.files[0].aidx_start.val, 0)
				self.assertEqual(w.files[0].aidx_end.val, 0)
				self.assertEqual(w.files[0].name.val, fname)

				w.close()


				# Compare binary data
				expected_dat = 'WIFFINFO'.encode('ascii')
				expected_dat += struct.pack("<QQ", 4096, 1)
				# WIFFINFO header
				expected_dat += struct.pack("<HHHHHHIHHQQQ", 44, 66, 88, 99, 155, 225, 12345, 2, 1, 0, 0, 0)
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
				expected_dat += struct.pack('<HH', 12,70)
				# File 0
				expected_dat += struct.pack('<HHHH', 0,0,0,0)
				expected_dat += struct.pack('<BHHQQQQ', 0, 37, 37+len(fname), 0,0, 0,0)
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

	def test_wave(self):
		"""
		Simple test to make a WIFFINFO & WIFFWAVE chunks and check that reading via class and binary match.
		"""
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				random.seed(0)

				frames = [
					[],
				]
				for i in range(10):
					frames[0].append( (struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12))) )

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
				w.set_file(fname)
				w.new_segment([0,1], segmentid=1)

				w.add_frames(*frames[0])

				self.assertEqual(w.start, s_date)
				self.assertEqual(w.end, e_date)
				self.assertEqual(w.description, "hello world")
				self.assertEqual(w.fs, 12345)
				self.assertEqual(w.num_channels, 2)
				self.assertEqual(w.num_files, 1)
				self.assertEqual(w.num_frames, 10)
				self.assertEqual(w.num_annotations, 0)
				self.assertEqual(w.num_metas, 0)

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
				self.assertEqual(w.files[0].aidx_start.val, 0)
				self.assertEqual(w.files[0].aidx_end.val, 0)
				self.assertEqual(w.files[0].name.val, fname)

				w.close()


				# Compare binary data
				expected_dat = 'WIFFINFO'.encode('ascii')
				expected_dat += struct.pack("<QQ", 4096, 1)
				# WIFFINFO header
				expected_dat += struct.pack("<HHHHHHIHHQQQ", 44, 66, 88, 99, 155, 225, 12345, 2, 1, 10, 0, 0)
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
				expected_dat += struct.pack('<HH', 12,70)
				# File 0
				expected_dat += struct.pack('<HHHH', 0,0,0,0)
				expected_dat += struct.pack('<BHHQQQQ', 0, 37, 37+len(fname), 0,10, 0,0)
				expected_dat += fname.encode('ascii')

				with open(fname, 'rb') as g:
					dat = g.read()
				self.maxDiff = None
				self.assertEqual(len(dat), 8192)
				# Compare non-zero data
				self.assertEqual(dat[0:len(expected_dat)].hex(), expected_dat.hex())
				self.assertEqual(dat[len(expected_dat):4096].hex(), '00'*(4096 - len(expected_dat)))


				expected_dat = 'WIFFWAVE'.encode('ascii')
				expected_dat += struct.pack("<QBBBBBBBB", 4096, ord('0'),0,0,0,1,0,0,0)
				# WIFFWAVE header
				expected_dat += struct.pack("<B", 3)
				expected_dat += struct.pack("<" + "B"*31, *([0]*31))
				expected_dat += struct.pack("<QQ", 0, 10)
				for i in range(len(frames[0])):
					f = frames[0][i]
					expected_dat += b''.join(f)

				self.assertEqual(dat[4096:4096+len(expected_dat)].hex(), expected_dat.hex())
				self.assertEqual(dat[4096+len(expected_dat):8192].hex(), '00'*(4096 - len(expected_dat)))

			finally:
				os.unlink(fname)

	def test_anno(self):
		"""
		Simple test to make a WIFFINFO & WIFFANNO chunks and check that reading via class and binary match.
		"""
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
				w.set_file(fname)
				w.new_annotations()

				w.add_annotation(typ='M', fidx=(10,20), marker='WXYZ')
				w.add_annotation(typ='D', fidx=(30,40), marker='ABCD', value=456789012345)
				w.add_annotation(typ='C', fidx=(15,25), comment="silly comment")

				self.assertEqual(w.start, s_date)
				self.assertEqual(w.end, e_date)
				self.assertEqual(w.description, "hello world")
				self.assertEqual(w.fs, 12345)
				self.assertEqual(w.num_channels, 2)
				self.assertEqual(w.num_files, 1)
				self.assertEqual(w.num_frames, 0)
				self.assertEqual(w.num_annotations, 3)
				self.assertEqual(w.num_metas, 0)

				self.assertEqual(w._chunks['INFO'].chunk.offset, 0)
				self.assertEqual(w._chunks['INFO'].chunk.magic, "WIFFINFO")
				self.assertEqual(w._chunks['INFO'].chunk.size, 4096)
				self.assertEqual(w._chunks['INFO'].offset, 24)

				self.assertEqual(w._chunks[fname][0].chunk.magic, 'WIFFINFO')
				self.assertEqual(w._chunks[fname][0].chunk.size, 4096)
				self.assertEqual(w._chunks[fname][0].chunk.offset, 0)
				self.assertEqual(w._chunks[fname][0].chunk.attributes[0], 1)
				for i in range(1,8):
					self.assertEqual(w._chunks[fname][0].chunk.attributes[i], 0, msg="i==%d"%i)

				self.assertEqual(w._chunks[fname][1].chunk.magic, 'WIFFANNO')
				self.assertEqual(w._chunks[fname][1].chunk.size, 4096*2)
				self.assertEqual(w._chunks[fname][1].chunk.offset, 4096)
				self.assertEqual(w._chunks[fname][1].chunk.attributes[0], ord('0'))
				for i in range(1,8):
					self.assertEqual(w._chunks[fname][1].chunk.attributes[i], 0, msg="i==%d"%i)

				self.assertEqual(w._current_annotations.aidx_start, 0)
				self.assertEqual(w._current_annotations.aidx_end, 3)
				self.assertEqual(w._current_annotations.fidx_first, 10)
				self.assertEqual(w._current_annotations.fidx_last, 40)
				self.assertEqual(w._current_annotations.num_annotations, 3)

				self.assertEqual(w.channels[0].name.val, "I")
				self.assertEqual(w.channels[0].unit.val, "uV")
				self.assertEqual(w.channels[0].bit.val, 12)
				self.assertEqual(w.channels[0].comment.val, "lead test I")

				self.assertEqual(w.channels[1].name.val, "X")
				self.assertEqual(w.channels[1].unit.val, "mA")
				self.assertEqual(w.channels[1].bit.val, 12)
				self.assertEqual(w.channels[1].comment.val, "lead test X")

				self.assertEqual(w.files[0].fidx_start.val, 10)
				self.assertEqual(w.files[0].fidx_end.val, 40)
				self.assertEqual(w.files[0].aidx_start.val, 0)
				self.assertEqual(w.files[0].aidx_end.val, 3)
				self.assertEqual(w.files[0].name.val, fname)

				a = w._current_annotations.annotations[0]
				self.assertEqual(a.type.val, 'M')
				self.assertEqual(a.fidx_start.val, 10)
				self.assertEqual(a.fidx_end.val, 20)
				a = a.condition_on('type')
				self.assertIsInstance(a, wiff.structs.ann_M_struct)
				self.assertEqual(a.marker.val, struct.unpack('<I', 'WXYZ'.encode('ascii'))[0])

				a = w._current_annotations.annotations[1]
				self.assertEqual(a.type.val, 'D')
				self.assertEqual(a.fidx_start.val, 30)
				self.assertEqual(a.fidx_end.val, 40)
				a = a.condition_on('type')
				self.assertIsInstance(a, wiff.structs.ann_D_struct)
				self.assertEqual(a.marker.val, struct.unpack('<I', 'ABCD'.encode('ascii'))[0])
				self.assertEqual(a.value.val, 456789012345)

				a = w._current_annotations.annotations[2]
				self.assertEqual(a.type.val, 'C')
				self.assertEqual(a.fidx_start.val, 15)
				self.assertEqual(a.fidx_end.val, 25)
				a = a.condition_on('type')
				self.assertIsInstance(a, wiff.structs.ann_C_struct)
				self.assertEqual(a.index_comment_start.val, 21)
				self.assertEqual(a.index_comment_end.val, 21 + len("silly comment"))
				self.assertEqual(a.comment.val, "silly comment")


				w.close()


				# Compare binary data
				expected_dat = 'WIFFINFO'.encode('ascii')
				expected_dat += struct.pack("<QQ", 4096, 1)
				# WIFFINFO header
				expected_dat += struct.pack("<HHHHHHIHHQQQ", 44, 66, 88, 99, 155, 225, 12345, 2, 1, 0, 3, 0)
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
				expected_dat += struct.pack('<HH', 12,70)
				# File 0
				expected_dat += struct.pack('<HHHH', 0,0,0,0)
				expected_dat += struct.pack('<BHHQQQQ', 0, 37, 37+len(fname), 10,40, 0,3)
				expected_dat += fname.encode('ascii')

				with open(fname, 'rb') as g:
					dat = g.read()
				self.maxDiff = None
				self.assertEqual(len(dat), 4096*3)
				# Compare non-zero data
				self.assertEqual(dat[0:len(expected_dat)].hex(), expected_dat.hex())
				self.assertEqual(dat[len(expected_dat):4096].hex(), '00'*(4096 - len(expected_dat)))

				expected_dat = 'WIFFANNO'.encode('ascii')
				expected_dat += struct.pack("<QBBBBBBBB", 4096*2, ord('0'),0,0,0,0,0,0,0)
				# WIFFANNO header
				expected_dat += struct.pack("<QQQQIH", 0,3, 10,40, 3, 38)
				expected_dat += struct.pack("<HHHHHH", 4034,4055, 4055,4084, 4084,4118)

				self.assertEqual(dat[4096:4096+len(expected_dat)].hex(), expected_dat.hex())
				self.assertEqual(dat[4096+len(expected_dat):2*4096].hex(), '00'*(4096 - len(expected_dat)))

				# M annotation
				expected_dat = struct.pack("<BQQ", ord('M'), 10,20)
				expected_dat += 'WXYZ'.encode('ascii')
				# D annotation
				expected_dat += struct.pack("<BQQ", ord('D'), 30,40)
				expected_dat += 'ABCD'.encode('ascii')
				expected_dat += struct.pack('<Q', 456789012345)
				# C annotation
				expected_dat += struct.pack("<BQQHH", ord('C'), 15,25, 21,34)
				expected_dat += 'silly comment'.encode('ascii')

				self.assertEqual(dat[2*4096:2*4096+len(expected_dat)].hex(), expected_dat.hex())
				self.assertEqual(dat[2*4096+len(expected_dat):3*4096].hex(), '00'*(4096 - len(expected_dat)))

			finally:
				os.unlink(fname)

	def test_multifile(self):
		"""
		Check that creating a second WIFFWAVE file matches reading through class and binary match.
		"""
		with tempfile.NamedTemporaryFile() as f:
			fname1 = f.name + '.wiff'
			fname2 = f.name + '-2.wiff'
			try:
				random.seed(0)

				frames = [
					[],
					[]
				]
				for i in range(10):
					frames[0].append( (struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12))) )
				for i in range(10):
					frames[1].append( (struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12))) )

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

				w.add_frames(*frames[0])

				w.new_file(fname2)
				w.new_segment([0,1], segmentid=2)
				w.add_frames(*frames[1])


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
				self.assertEqual(w.num_metas, 0)

				self.assertEqual(w._chunks['INFO'].chunk.offset, 0)
				self.assertEqual(w._chunks['INFO'].chunk.magic, "WIFFINFO")
				self.assertEqual(w._chunks['INFO'].chunk.size, 4096)

				self.assertEqual(w._chunks[fname1][0].chunk.magic, "WIFFINFO")
				self.assertEqual(w._chunks[fname1][0].chunk.size, 4096)
				self.assertEqual(w._chunks[fname1][0].chunk.offset, 0)

				self.assertEqual(w._chunks[fname1][1].chunk.magic, "WIFFWAVE")
				self.assertEqual(w._chunks[fname1][1].chunk.size, 4096)
				self.assertEqual(w._chunks[fname1][0].chunk.offset, 0)

				self.assertEqual(w._chunks[fname2][0].chunk.magic, 'WIFFWAVE')
				self.assertEqual(w._chunks[fname2][0].chunk.size, 4096)
				self.assertEqual(w._chunks[fname2][0].chunk.offset, 0)

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
				self.assertEqual(w.files[0].aidx_start.val, 0)
				self.assertEqual(w.files[0].aidx_end.val, 0)
				self.assertEqual(w.files[0].name.val, fname1)

				self.assertEqual(w.files[1].fidx_start.val, 10)
				self.assertEqual(w.files[1].fidx_end.val, 20)
				self.assertEqual(w.files[1].aidx_start.val, 0)
				self.assertEqual(w.files[1].aidx_end.val, 0)
				self.assertEqual(w.files[1].name.val, fname2)


				expected_dat = 'WIFFINFO'.encode('ascii')
				expected_dat += struct.pack("<QQ", 4096, 1)
				# WIFFINFO header
				expected_dat += struct.pack("<HHHHHHIHHQQQ", 44, 66, 88, 99, 155, 285, 12345, 2, 2, 20, 0, 0)
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
				expected_dat += struct.pack('<HHHH', 12,70, 70,130)
				expected_dat += struct.pack('<HH', 0,0)
				# File 0
				expected_dat += struct.pack('<BHHQQQQ', 0, 37, 37+len(fname1), 0,10, 0,0)
				expected_dat += fname1.encode('ascii')
				# File 1
				expected_dat += struct.pack('<BHHQQQQ', 1, 37, 37+len(fname2), 10,20, 0,0)
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



				expected_dat = 'WIFFWAVE'.encode('ascii')
				expected_dat += struct.pack("<QBBBBBBBB", 4096, ord('0'),0,0,0,1,0,0,0)
				# WIFFWAVE header
				expected_dat += struct.pack("<B", 3)
				expected_dat += struct.pack("<" + "B"*31, *([0]*31))
				expected_dat += struct.pack("<QQ", 0, 10)
				for i in range(len(frames[0])):
					f = frames[0][i]
					expected_dat += b''.join(f)

				self.assertEqual(dat[4096:4096+len(expected_dat)].hex(), expected_dat.hex())


				with open(fname2, 'rb') as g:
					dat = g.read()
				#print(dat)
				self.assertEqual(len(dat), 4096)


			finally:
				os.unlink(fname1)
				os.unlink(fname2)

	def test_meta(self):
		"""
		Tests if meta values work correctly.
		"""
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
				self.assertEqual(w.num_metas, 0)

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
				self.assertEqual(w.files[0].aidx_start.val, 0)
				self.assertEqual(w.files[0].aidx_end.val, 0)
				self.assertEqual(w.files[0].name.val, fname)

				w.set_file(fname)
				w.new_metas()
				w.add_meta('channel', 1, "source.brand", "Tektronix")

				w.close()


				# Compare binary data
				expected_dat = 'WIFFINFO'.encode('ascii')
				expected_dat += struct.pack("<QQ", 4096, 1)
				# WIFFINFO header
				#expected_dat += struct.pack("<HHHHHHIHHQQQ", 44, 66, 88, 99, 155, 225, 12345, 2, 1, 0, 0, 1)
				expected_dat += struct.pack("<HHHHHHIHHQQQ", 44, 66, 88, 99, 155, 225, 12345, 2, 1, 0, 0, 0)
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
				expected_dat += struct.pack('<HH', 12,70)
				# File 0
				expected_dat += struct.pack('<HHHH', 0,0,0,0)
				expected_dat += struct.pack('<BHHQQQQ', 0, 37, 37+len(fname), 0,0, 0,0)
				expected_dat += fname.encode('ascii')

				# Make HEX (easier to view diff strings than binary)
				expected_dat = expected_dat.hex()

				with open(fname, 'rb') as g:
					dat = g.read()
				self.maxDiff = None
				self.assertEqual(len(dat), 4096*3)
				# Compare non-zero data
				self.assertEqual(dat[0:len(expected_dat)].hex(), expected_dat)
				self.assertEqual(dat[len(expected_dat):4096].hex(), '00'*(4096 - len(expected_dat)))

			finally:
				os.unlink(fname)

