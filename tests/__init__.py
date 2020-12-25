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

def getschema(fname):
	s = subprocess.run(['sqlite3', fname, '.dump'], stdout=subprocess.PIPE)
	return s.stdout

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
				'unit': 'V',
				'comment': 'Left channel',
			},
			{
				'idx': 1,
				'name': 'right',
				'bits': 16,
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
				self.assertEqual(c.name, 'left')
				self.assertEqual(c.unit, 'V')
				self.assertEqual(c.comment, 'Left channel')

				c = w.channel[2]
				self.assertEqual(c.id_recording, 1)
				self.assertEqual(c.idx, 1)
				self.assertEqual(c.bits, 16)
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

	def test_addannotation(self):
		with tempfile.NamedTemporaryFile() as f:
			fname = f.name + '.wiff'
			try:
				props = getprops()

				w = wiff.new(fname, props)
				w.add_segment(1, (1,2), 0, 2, b'hihihohobobo')

				self.assertEqual(len(w.annotation), 0)
				w.add_annotation(1, 0,1, 'M', None, 'FIFO', None)
				self.assertEqual(len(w.annotation), 1)

				a = w.annotation[1]
				self.assertEqual(a.fidx_start, 0)
				self.assertEqual(a.fidx_end, 1)
				self.assertEqual(a.type, 'M')
				self.assertEqual(a.comment, None)
				self.assertEqual(a.marker, 'FIFO')
				self.assertEqual(a.data, None)

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
					(b'hi', b'ih'),
					(b'ho', b'oh'),
					(b'ob', b'bo'),

					(b'xi', b'ix'),
					(b'to', b'ot'),
					(b'nu', b'un'),

					(b'ra', b'ar'),
					(b'ta', b'at'),
					(b'pa', b'ap')
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
					(b'hi', b'ih'),
					(b'ho', b'oh'),
					(b'ob', b'bo'),

					(b'xi', b'ix'),
					(b'to', b'ot'),
					(b'nu', b'un'),

					(b'ra', b'ar'),
					(b'ta', b'at'),
					(b'pa', b'ap')
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

				# Get the frame table
				ft = r.frame_table

				self.assertEqual(ft.fidx_start, 1)
				self.assertEqual(ft.fidx_end, 9)

				self.assertIsNotNone(ft.get_segment(1))
				self.assertIsNotNone(ft.get_segment(2))
				self.assertIsNotNone(ft.get_segment(3))
				self.assertIsNotNone(ft.get_segment(4))
				self.assertIsNotNone(ft.get_segment(5))
				self.assertIsNotNone(ft.get_segment(6))
				self.assertIsNotNone(ft.get_segment(7))
				self.assertIsNotNone(ft.get_segment(8))
				self.assertIsNotNone(ft.get_segment(9))

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
				for i in range(10, 100):
					self.assertRaises(ValueError, ft.get_segment, i)

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

