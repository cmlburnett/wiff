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

				w.add_segment(0, (0,1), 0, 2, b'hihihohobobo')

				self.assertEqual(len(w.segment), 1)
				s = w.segment[1]
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
				self.assertEqual(c.id_channel, 0)

				c = w.channelset[2]
				self.assertEqual(c.set, 1)
				self.assertEqual(c.id_channel, 1)


				#print(getschema(fname).decode('ascii'))
			finally:
				os.unlink(fname)

