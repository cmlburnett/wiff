import wiff

import datetime
import unittest
import tempfile
import os
import random
import struct
import subprocess

import logging

logging.basicConfig(level=logging.INFO)

def getprops():
	props = {
		'start': datetime.datetime.utcnow(),
		'end': datetime.datetime.utcnow(),
		'description': 'Test file',
		'fs': 1000,
		'channels': [
			{
				'idx': 0,
				'name': 'left',
				'bits': 16,
				'storage': 2,
				'unit': 'V',
				'comment': 'Left channel',
			},
			{
				'idx': 1,
				'name': 'right',
				'bits': 16,
				'storage': 3,
				'unit': 'V',
				'comment': 'Right channel',
			},
		],
	}
	return props

class SimpleTests(unittest.TestCase):
	def test_basicsetup(self):
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)


				self.assertEqual(len(w.recording), 1)
				r = w.recording[1]
				self.assertEqual(r.id, 1)
				self.assertEqual(r.start, props['start'])
				self.assertEqual(r.end, props['end'])
				self.assertEqual(r.description, props['description'])
				self.assertEqual(r.sampling, props['fs'])

				self.assertEqual(len(w.channel), 2)
				c = w.channel[1]
				self.assertEqual(c.id_recording, 1)
				self.assertEqual(c.idx, 0)
				self.assertEqual(c.bits, 16)
				self.assertEqual(c.storage, 2)
				self.assertEqual(c.name, 'left')
				self.assertEqual(c.unit, 'V')
				self.assertEqual(c.comment, 'Left channel')

				c = w.channel[2]
				self.assertEqual(c.id_recording, 1)
				self.assertEqual(c.idx, 1)
				self.assertEqual(c.bits, 16)
				self.assertEqual(c.storage, 3)
				self.assertEqual(c.name, 'right')
				self.assertEqual(c.unit, 'V')
				self.assertEqual(c.comment, 'Right channel')

				self.assertEqual(len(w.meta), 2)
				m = w.meta[1]
				self.assertEqual(m.key, 'WIFF.version')
				self.assertEqual(m.type, 'int')
				self.assertEqual(m.raw_value, '2')
				self.assertEqual(m.value, 2)

				m = w.meta[2]
				self.assertEqual(m.key, 'WIFF.ctime')
				self.assertEqual(m.type, 'datetime')

				# Can't get the date so just makes ure it's close
				t = m.value
				now = datetime.datetime.utcnow()
				diff = now - t
				self.assertEqual(diff.days, 0)
				self.assertEqual(diff.seconds, 0)
				# Don't care about microseconds

				self.assertEqual(len(w.segment), 0)
				self.assertEqual(len(w.annotation), 0)
				self.assertEqual(len(w.channelset), 0)

			finally:
				os.unlink(fname)

	def test_addsegment(self):
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)


				self.assertEqual(len(w.segment), 0)

				w.add_segment(1, (1,2), 0, 2, b'hihihohobobo')

				self.assertEqual(len(w.segment), 1)
				s = w.segment[1]
				self.assertEqual(s.id_recording, 1)
				self.assertEqual(s.id, 1)
				self.assertEqual(s.idx, 1)
				self.assertEqual(s.fidx_start, 0)
				self.assertEqual(s.fidx_end, 2)
				self.assertEqual(s.channelset_id, 1)
				self.assertEqual(s.stride, 5)
				self.assertEqual(s.id_blob, 1)

				self.assertEqual(len(w.blob), 1)
				b = s.blob
				self.assertEqual(b.id, 1)
				self.assertEqual(b.compression, None)
				self.assertEqual(b.data, b'hihihohobobo')

				self.assertEqual(len(w.channelset), 2)
				c = w.channelset[1]
				self.assertEqual(c.set, 1)
				self.assertEqual(c.id_channel, 1)

				c = w.channelset[2]
				self.assertEqual(c.set, 1)
				self.assertEqual(c.id_channel, 2)

			finally:
				os.unlink(fname)

	def test_addrecordings_segments(self):
		"""
		Check that WIFF_recording_segments filters appropriately
		"""
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()
				props2 = getprops()
				props2['description'] = 'Second test'
				props2['fs'] = 10000

				w = wiff.new(fname, props)

				# Add a second recording
				self.assertEqual(len(w.recording), 1)
				w.add_recording(props2['start'], props2['end'], props2['description'], props2['fs'], props2['channels'])
				self.assertEqual(len(w.recording), 2)

				r = w.recording[1]
				self.assertEqual(r.id, 1)
				self.assertEqual(r.start, props['start'])
				self.assertEqual(r.end, props['end'])
				self.assertEqual(r.description, props['description'])
				self.assertEqual(r.sampling, props['fs'])

				r = w.recording[2]
				self.assertEqual(r.id, 2)
				self.assertEqual(r.start, props2['start'])
				self.assertEqual(r.end, props2['end'])
				self.assertEqual(r.description, props2['description'])
				self.assertEqual(r.sampling, props2['fs'])


				self.assertEqual(len(w.segment), 0)
				w.add_segment(1, (1,2), 0, 2, b'hihihohobobo')
				self.assertEqual(len(w.segment), 1)


				r = w.recording[1]
				self.assertEqual(len(r.segment), 1)

				r = w.recording[2]
				self.assertEqual(len(r.segment), 0)

			finally:
				os.unlink(fname)

	def test_addrecordings_metas(self):
		"""
		Check that WIFF_recording_meta filters appropriately
		"""
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()
				props2 = getprops()
				props2['description'] = 'Second test'
				props2['fs'] = 10000

				w = wiff.new(fname, props)

				# Add a second recording
				self.assertEqual(len(w.recording), 1)
				w.add_recording(props2['start'], props2['end'], props2['description'], props2['fs'], props2['channels'])
				self.assertEqual(len(w.recording), 2)

				self.assertEqual(len(w.meta), 2)

				r = w.recording[1]
				self.assertEqual(len(r.meta), 0)

				r = w.recording[2]
				self.assertEqual(len(r.meta), 0)


				w.add_meta(2, 'test', 'int', 10)

				r = w.recording[1]
				self.assertEqual(len(r.meta), 0)

				r = w.recording[2]
				self.assertEqual(len(r.meta), 1)

				m = r.meta.values()[0]
				self.assertEqual(m.key, 'test')
				self.assertEqual(m.type, 'int')
				self.assertEqual(m.raw_value, '10')
				self.assertEqual(m.value, 10)

			finally:
				os.unlink(fname)


	def test_addrecordings_channels(self):
		"""
		Check that WIFF_recording_channels filters appropriately
		"""
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()
				props2 = getprops()
				props2['description'] = 'Second test'
				props2['fs'] = 10000
				props2['channels'][0]['unit'] = 'uV'
				props2['channels'][1]['unit'] = 'uV'

				w = wiff.new(fname, props)

				# Add a second recording
				self.assertEqual(len(w.recording), 1)
				w.add_recording(props2['start'], props2['end'], props2['description'], props2['fs'], props2['channels'])
				self.assertEqual(len(w.recording), 2)


				self.assertEqual(len(w.channel), 4)

				r = w.recording[1]
				cs = r.channel.keys()
				self.assertEqual(len(r.channel), 2)
				self.assertEqual(r.channel[cs[0]].unit, 'V')
				self.assertEqual(r.channel[cs[1]].unit, 'V')

				r = w.recording[2]
				cs = r.channel.keys()
				self.assertEqual(len(r.channel), 2)
				self.assertEqual(r.channel[cs[0]].unit, 'uV')
				self.assertEqual(r.channel[cs[1]].unit, 'uV')

			finally:
				os.unlink(fname)

	def test_frame(self):
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				frames = [
					None,
					(b'hi', b'\x00ih'),
					(b'ho', b'\x00oh'),
					(b'ob', b'\x00bo'),

					(b'xi', b'\x00ix'),
					(b'to', b'\x00ot'),
					(b'nu', b'\x00un'),

					(b'ra', b'\x00ar'),
					(b'ta', b'\x00at'),
					(b'pa', b'\x00ap')
				]

				# Combine into strings
				fs = [
					frames[1][0] + frames[1][1] + frames[2][0] + frames[2][1] + frames[3][0] + frames[3][1],
					frames[4][0] + frames[4][1] + frames[5][0] + frames[5][1] + frames[6][0] + frames[6][1],
					frames[7][0] + frames[7][1] + frames[8][0] + frames[8][1] + frames[9][0] + frames[9][1]
				]

				# Add segments
				r = w.recording[1]
				w.add_segment(1, (1,2), 1, 3, fs[0])
				w.add_segment(1, (1,2), 4, 6, fs[1])
				w.add_segment(1, (1,2), 7, 9, fs[2])

				# Test each frame
				f = r.frame[1]
				self.assertEqual(f, frames[1])

				f = r.frame[2]
				self.assertEqual(f, frames[2])

				f = r.frame[3]
				self.assertEqual(f, frames[3])

				f = r.frame[4]
				self.assertEqual(f, frames[4])

				f = r.frame[5]
				self.assertEqual(f, frames[5])

				f = r.frame[6]
				self.assertEqual(f, frames[6])

				f = r.frame[7]
				self.assertEqual(f, frames[7])

				f = r.frame[8]
				self.assertEqual(f, frames[8])

				f = r.frame[9]
				self.assertEqual(f, frames[9])

				# Test mid slice
				fs = r.frame[2:4]
				self.assertEqual(len(fs), 2)
				self.assertEqual(fs[0], frames[2])
				self.assertEqual(fs[1], frames[3])

				# Test open start slice
				fs = r.frame[:3]
				self.assertEqual(len(fs), 2)
				self.assertEqual(fs[0], frames[1])
				self.assertEqual(fs[1], frames[2])

				# Test open end slice
				fs = r.frame[7:]
				self.assertEqual(len(fs), 3)
				self.assertEqual(fs[0], frames[7])
				self.assertEqual(fs[1], frames[8])
				self.assertEqual(fs[2], frames[9])

			finally:
				os.unlink(fname)

	def test_frametable(self):
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				frames = [
					None,
					(b'hi', b'\x00ih'),
					(b'ho', b'\x00oh'),
					(b'ob', b'\x00bo'),

					(b'xi', b'\x00ix'),
					(b'to', b'\x00ot'),
					(b'nu', b'\x00un'),

					(b'ra', b'\x00ar'),
					(b'ta', b'\x00at'),
					(b'pa', b'\x00ap')
				]

				# Combine into strings
				fs = [
					None,
					frames[1][0] + frames[1][1] + frames[2][0] + frames[2][1] + frames[3][0] + frames[3][1],
					frames[4][0] + frames[4][1] + frames[5][0] + frames[5][1] + frames[6][0] + frames[6][1],
					frames[7][0] + frames[7][1] + frames[8][0] + frames[8][1] + frames[9][0] + frames[9][1]
				]

				# Add segments
				r = w.recording[1]
				w.add_segment(1, (1,2), 1, 3, fs[1])
				w.add_segment(1, (1,2), 4, 6, fs[2])
				w.add_segment(1, (1,2), 7, 9, fs[3])

				# Get the frame table
				ft = r.frame_table

				self.assertEqual(ft.fidx_start, 1)
				self.assertEqual(ft.fidx_end, 9)

				# Ensure segments are returned
				self.assertIsNotNone(ft.get_segment(1))
				self.assertIsNotNone(ft.get_segment(2))
				self.assertIsNotNone(ft.get_segment(3))
				self.assertIsNotNone(ft.get_segment(4))
				self.assertIsNotNone(ft.get_segment(5))
				self.assertIsNotNone(ft.get_segment(6))
				self.assertIsNotNone(ft.get_segment(7))
				self.assertIsNotNone(ft.get_segment(8))
				self.assertIsNotNone(ft.get_segment(9))

				# Check that segments are returned correctly
				self.assertEqual(ft.get_segment(1).fidx_start, 1)
				self.assertEqual(ft.get_segment(1).fidx_end, 3)
				self.assertEqual(ft.get_segment(2).fidx_start, 1)
				self.assertEqual(ft.get_segment(2).fidx_end, 3)
				self.assertEqual(ft.get_segment(3).fidx_start, 1)
				self.assertEqual(ft.get_segment(3).fidx_end, 3)
				self.assertEqual(ft.get_segment(4).fidx_start, 4)
				self.assertEqual(ft.get_segment(4).fidx_end, 6)
				self.assertEqual(ft.get_segment(5).fidx_start, 4)
				self.assertEqual(ft.get_segment(5).fidx_end, 6)
				self.assertEqual(ft.get_segment(6).fidx_start, 4)
				self.assertEqual(ft.get_segment(6).fidx_end, 6)
				self.assertEqual(ft.get_segment(7).fidx_start, 7)
				self.assertEqual(ft.get_segment(7).fidx_end, 9)
				self.assertEqual(ft.get_segment(8).fidx_start, 7)
				self.assertEqual(ft.get_segment(8).fidx_end, 9)
				self.assertEqual(ft.get_segment(9).fidx_start, 7)
				self.assertEqual(ft.get_segment(9).fidx_end, 9)

				# Just test some range of values, obviously can't be exhaustive
				#   -10 through 0 should throw ValueError exceptions
				for i in range(-10, 1):
					self.assertRaises(ValueError, ft.get_segment, i)
				#   +10 and higher should also throw ValueError exceptions
				for i in range(10, 100):
					self.assertRaises(ValueError, ft.get_segment, i)

				# Compare frame data
				self.assertEqual(ft[1], frames[1])
				self.assertEqual(ft[2], frames[2])
				self.assertEqual(ft[3], frames[3])

			finally:
				os.unlink(fname)

	def test_annotation(self):
		""" Test annotations """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)
				w.add_segment(1, (1,2), 0, 2, b'hi\x00hiho\x00hobo\x00bo')
				w.add_segment(1, (1,2), 3, 4, b'hi\x00hiho\x00hobo\x00bo')
				w.add_segment(1, (1,2), 5, 6, b'hi\x00hiho\x00hobo\x00bo')

				# Get the recording
				r = w.recording[1]

				self.assertEqual(len(w.annotation), 0)
				self.assertEqual(len(r.annotation), 0)

				w.add_annotation_C(1, 2,4, "Testing a comment")
				self.assertEqual(len(w.annotation), 1)
				self.assertEqual(len(r.annotation), 1)

				w.add_annotation_M(1, 3,6, "STOP")
				self.assertEqual(len(w.annotation), 2)
				self.assertEqual(len(r.annotation), 2)

				w.add_annotation_D(1, 1,1, "STRT", 52)
				self.assertEqual(len(w.annotation), 3)
				self.assertEqual(len(r.annotation), 3)


				self.assertEqual(w.annotation[1].type, 'C')
				self.assertEqual(w.annotation[2].type, 'M')
				self.assertEqual(w.annotation[3].type, 'D')

				self.assertEqual(w.annotation[1].comment, 'Testing a comment')
				self.assertIsNone(w.annotation[1].marker)
				self.assertIsNone(w.annotation[1].data)

				self.assertIsNone(w.annotation[2].comment)
				self.assertEqual(w.annotation[2].marker, 'STOP')
				self.assertIsNone(w.annotation[2].data)

				self.assertIsNone(w.annotation[3].comment)
				self.assertEqual(w.annotation[3].marker, 'STRT')
				self.assertEqual(w.annotation[3].data, 52)

			finally:
				os.unlink(fname)

	def test_meta_file(self):
		""" Test meta values against the file """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				w.add_segment(1, (1,2), 0, 2, b'hi\x00hiho\x00hobo\x00bo')
				w.add_segment(1, (1,2), 3, 4, b'hi\x00hiho\x00hobo\x00bo')
				w.add_segment(1, (1,2), 5, 6, b'hi\x00hiho\x00hobo\x00bo')

				dt = datetime.datetime.utcnow()

				r = w.recording[1]

				# Accumulate meta ids here
				a = {}

				self.assertEqual(len(w.meta), 2)
				self.assertEqual(len(r.meta), 0)
				a[1] = w.add_meta_int(None, 'fooint', 42)

				self.assertEqual(len(w.meta), 3)
				self.assertEqual(len(r.meta), 0)
				a[2] = w.add_meta_str(None, 'foostr', 'boo')

				self.assertEqual(len(w.meta), 4)
				self.assertEqual(len(r.meta), 0)
				a[3] = w.add_meta_bool(None, 'footrue', True)

				self.assertEqual(len(w.meta), 5)
				self.assertEqual(len(r.meta), 0)
				a[4] = w.add_meta_bool(None, 'foofalse', False)

				self.assertEqual(len(w.meta), 6)
				self.assertEqual(len(r.meta), 0)
				a[5] = w.add_meta_datetime(None, 'foodt', dt)


				self.assertEqual(w.meta[a[1]].key, 'fooint')
				self.assertEqual(w.meta[a[1]].type, 'int')
				self.assertEqual(w.meta[a[1]].value, 42)
				self.assertEqual(w.meta[a[1]].raw_value, '42')

				self.assertEqual(w.meta[a[2]].key, 'foostr')
				self.assertEqual(w.meta[a[2]].type, 'str')
				self.assertEqual(w.meta[a[2]].value, 'boo')
				self.assertEqual(w.meta[a[2]].raw_value, 'boo')

				self.assertEqual(w.meta[a[3]].key, 'footrue')
				self.assertEqual(w.meta[a[3]].type, 'bool')
				self.assertEqual(w.meta[a[3]].value, True)
				self.assertEqual(w.meta[a[3]].raw_value, '1')

				self.assertEqual(w.meta[a[4]].key, 'foofalse')
				self.assertEqual(w.meta[a[4]].type, 'bool')
				self.assertEqual(w.meta[a[4]].value, False)
				self.assertEqual(w.meta[a[4]].raw_value, '0')

				self.assertEqual(w.meta[a[5]].key, 'foodt')
				self.assertEqual(w.meta[a[5]].type, 'datetime')
				self.assertEqual(w.meta[a[5]].value, dt)
				self.assertEqual(w.meta[a[5]].raw_value, dt.strftime("%Y-%m-%d %H:%M:%S.%f"))



				# Search for them
				c = w.meta.find(None, 'fooint')
				self.assertIsNotNone(c)
				self.assertEqual(len(c), 1)
				self.assertEqual(c[0].id, a[1])
				self.assertEqual(c[0].key, 'fooint')
				self.assertEqual(c[0].value, 42)

				c = w.meta.find(None, 'foostr')
				self.assertIsNotNone(c)
				self.assertEqual(len(c), 1)
				self.assertEqual(c[0].id, a[2])
				self.assertEqual(c[0].key, 'foostr')

				c = w.meta.find(None, 'gibberish')
				self.assertIsNotNone(c)
				self.assertEqual(len(c), 0)

				# Metas apply to file not a recording
				c = w.meta.find(1, 'fooint')
				self.assertIsNotNone(c)
				self.assertEqual(len(c), 0)

			finally:
				os.unlink(fname)

	def test_meta_recording(self):
		""" Test meta values against a recording """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				w.add_segment(1, (1,2), 0, 2, b'hi\x00hiho\x00hobo\x00bo')
				w.add_segment(1, (1,2), 3, 4, b'hi\x00hiho\x00hobo\x00bo')
				w.add_segment(1, (1,2), 5, 6, b'hi\x00hiho\x00hobo\x00bo')

				dt = datetime.datetime.utcnow()

				r = w.recording[1]

				# Accumulate meta ids here
				a = {}

				self.assertEqual(len(w.meta), 2)
				self.assertEqual(len(r.meta), 0)
				a[1] = w.add_meta_int(1, 'fooint', 42)

				self.assertEqual(len(w.meta), 3)
				self.assertEqual(len(r.meta), 1)
				a[2] = w.add_meta_str(r.id, 'foostr', 'boo')

				self.assertEqual(len(w.meta), 4)
				self.assertEqual(len(r.meta), 2)
				a[3] = w.add_meta_bool(r.id, 'footrue', True)

				self.assertEqual(len(w.meta), 5)
				self.assertEqual(len(r.meta), 3)
				a[4] = w.add_meta_bool(r.id, 'foofalse', False)

				self.assertEqual(len(w.meta), 6)
				self.assertEqual(len(r.meta), 4)
				a[5] = w.add_meta_datetime(r.id, 'foodt', dt)


				self.assertEqual(r.meta[a[1]].key, 'fooint')
				self.assertEqual(r.meta[a[1]].type, 'int')
				self.assertEqual(r.meta[a[1]].value, 42)
				self.assertEqual(r.meta[a[1]].raw_value, '42')

				self.assertEqual(r.meta[a[2]].key, 'foostr')
				self.assertEqual(r.meta[a[2]].type, 'str')
				self.assertEqual(r.meta[a[2]].value, 'boo')
				self.assertEqual(r.meta[a[2]].raw_value, 'boo')

				self.assertEqual(r.meta[a[3]].key, 'footrue')
				self.assertEqual(r.meta[a[3]].type, 'bool')
				self.assertEqual(r.meta[a[3]].value, True)
				self.assertEqual(r.meta[a[3]].raw_value, '1')

				self.assertEqual(r.meta[a[4]].key, 'foofalse')
				self.assertEqual(r.meta[a[4]].type, 'bool')
				self.assertEqual(r.meta[a[4]].value, False)
				self.assertEqual(r.meta[a[4]].raw_value, '0')

				self.assertEqual(r.meta[a[5]].key, 'foodt')
				self.assertEqual(r.meta[a[5]].type, 'datetime')
				self.assertEqual(r.meta[a[5]].value, dt)
				self.assertEqual(r.meta[a[5]].raw_value, dt.strftime("%Y-%m-%d %H:%M:%S.%f"))

			finally:
				os.unlink(fname)

	def test_meta_find_wild(self):
		""" Test dotted structure of meta finding """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				c = w.meta.find(None, 'WIFF.*')
				start_cnt = len(c)


				self.assertEqual(len(c), start_cnt)
				aid = w.add_meta_int(None, "WIFF.monkey", 99)

				c = w.meta.find_as_dict(None, 'WIFF.*')
				self.assertEqual(len(c), start_cnt+1)
				self.assertTrue('WIFF.monkey' in c)
				self.assertEqual(c['WIFF.monkey'].id, aid)
				self.assertEqual(c['WIFF.monkey'].key, 'WIFF.monkey')
				self.assertEqual(c['WIFF.monkey'].value, 99)

			finally:
				os.unlink(fname)

	def test_meta_duplicate_keys(self):
		""" Test duplicate meta keys """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				c = w.meta.find(None, 'WIFF.*')
				start_cnt = len(c)


				self.assertEqual(len(c), start_cnt)
				# Add key to recording
				aid = w.add_meta_int(None, "WIFF.monkey", 99)

				c = w.meta.find_as_dict(None, 'WIFF.*')
				self.assertEqual(len(c), start_cnt+1)
				self.assertTrue('WIFF.monkey' in c)
				self.assertEqual(c['WIFF.monkey'].id, aid)
				self.assertEqual(c['WIFF.monkey'].key, 'WIFF.monkey')
				self.assertEqual(c['WIFF.monkey'].value, 99)
				cid = c['WIFF.monkey'].id

				# Should throw exception for duplicating key on the file
				self.assertRaises(ValueError, w.add_meta_int, None, "WIFF.monkey", 98)

				# Should NOT throw exception as this is adding to a recording
				aid = w.add_meta_int(1, "WIFF.monkey", 97)
				self.assertEqual(w.meta[aid].key, 'WIFF.monkey')
				self.assertEqual(w.meta[aid].value, 97)


				props2 = getprops()
				props2['description'] = 'Second test'
				props2['fs'] = 10000

				# Add a second recording
				self.assertEqual(len(w.recording), 1)
				w.add_recording(props2['start'], props2['end'], props2['description'], props2['fs'], props2['channels'])
				self.assertEqual(len(w.recording), 2)

				# Should NOT throw exception as this is adding to a second recording
				bid = w.add_meta_int(2, "WIFF.monkey", 96)
				self.assertEqual(w.meta[bid].key, 'WIFF.monkey')
				self.assertEqual(w.meta[bid].value, 96)

				# Check that the other key wasn't modified (on first recording)
				self.assertEqual(w.meta[aid].key, 'WIFF.monkey')
				self.assertEqual(w.meta[aid].value, 97)

				# Check that the other key wasn't modified (on file)
				self.assertEqual(w.meta[cid].key, 'WIFF.monkey')
				self.assertEqual(w.meta[cid].value, 99)

				# I could rename but don't want to
				#cid = id_recording=None
				#aid = id_recording=1
				#bid = id_recording=2

			finally:
				os.unlink(fname)

	def test_open_verify(self):
		""" Create a schema and read it back """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)
				w.close()

				# Opening is successful
				w = wiff.open(fname)

			finally:
				os.unlink(fname)

	def test_open_fail_extra_table(self):
		""" Create a schema and fail by having an extra table """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				# Create an extra table
				w.db.begin()
				w.db.execute("create table `foo` (`bar` text)")
				w.db.commit()
				w.close()

				# Should fail
				self.assertRaises(Exception, wiff.open, fname)

			finally:
				os.unlink(fname)

	def test_open_fail_absent_table(self):
		""" Create a schema and fail by having an absent table """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

				# Create an extra table
				w.db.begin()
				w.db.execute("drop table `meta`")
				w.db.commit()
				w.close()

				# Should fail
				self.assertRaises(Exception, wiff.open, fname)

			finally:
				os.unlink(fname)

	def template(self):
		""" Copy this to start a new test """
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)

			finally:
				os.unlink(fname)

