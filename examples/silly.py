import datetime
import os.path
import random
import struct
import time

import wiff
from bstruct import *

def main1(fname):
	props = {
		'start': datetime.datetime.utcnow(),
		'end': datetime.datetime.utcnow(),
		'description': 'Test WIFF file description and this one is even longer and crazier!',
		'fs': 500,
		'channels': [],
		'files': [],
	}
	leads = ['I', 'II', 'III', 'aVL', 'aVR', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
	for lead in leads:
		props['channels'].append( {'name': lead, 'bit': 12, 'unit': 'uV', 'comment': 'Lead ' + lead} )

	# Create
	w = wiff.new(fname, props, force=True)

	# Then re-open just to test
	w = wiff.open(fname)

	w.set_file(fname)

	random.seed(0)

	v = w.new_segment(w.channels[0:2], segmentid=1)
	v.frame_space = 1006
	frames = []
	for i in range(100):
		frames.append( (struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12))) )
	w.add_frames(*frames)

	v = w.new_segment(w.channels[0:2], segmentid=2)
	v.frame_space = 1006
	frames = []
	for i in range(100):
		frames.append( (struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12))) )
	w.add_frames(*frames)


def main2(fname):
	# Reopen again
	w = wiff.open(fname)

	w.set_file(fname)
	w.new_annotations()
	w.add_annotation(typ='M', fidx=(10,20), marker='STAT')
	w.add_annotation(typ='C', fidx=(20,30), comment='Hello annotation world')
	w.add_annotation(typ='M', fidx=(30,40), marker='stat')
	w.add_annotation(typ='D', fidx=(30,40), marker='stat', value=123456789)

	wavs = list(w._GetWAVE())

	v = w.new_segment(wavs[-1].channels, 3)
	v.frame_space = 1006
	frames = []
	for i in range(100):
		frames.append( (struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12))) )
	w.add_frames(*frames)

	print(w.dumps_str())

def main3(fname):
	props = {
		'start': datetime.datetime.utcnow(),
		'end': datetime.datetime.utcnow(),
		'description': 'Test WIFF file description and this one is even longer and crazier!',
		'fs': 500,
		'channels': [],
		'files': [],
	}
	leads = ['I', 'II', 'III', 'aVL', 'aVR', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
	for lead in leads:
		props['channels'].append( {'name': lead, 'bit': 12, 'unit': 'uV', 'comment': 'Lead ' + lead} )

	# Create
	w = wiff.new(fname, props, force=True)

	# Then re-open just to test
	w = wiff.open(fname)

	w.set_file(fname)

	random.seed(0)

	v = w.new_segment(w.channels[0:2], segmentid=1)
	v.frame_space = 10000
	frames = []
	for i in range(10000):
		frames.append( (struct.pack(">H", random.getrandbits(12)), struct.pack(">H", random.getrandbits(12))) )
	w.add_frames(*frames)

	base,ext = os.path.splitext(fname)
	annos_fname = base + '_anno' + ext

	w.new_file(annos_fname)
	w.new_annotations()
	w.add_annotation(typ='M', fidx=(10,20), marker='STAT')
	w.add_annotation(typ='C', fidx=(20,30), comment='Hello annotation world')
	w.add_annotation(typ='M', fidx=(30,40), marker='stat')
	w.add_annotation(typ='D', fidx=(30,40), marker='stat', value=123456789)

	print(w.dumps_str())

	annos = w.get_annotations()
	print(list(annos))
	annos = w.get_annotations(typ='M')
	print(list(annos))
	annos = w.get_annotations(fidx=200)
	print(list(annos))
	annos = w.get_annotations(fname=fname)
	print(list(annos))
	annos = w.get_annotations(fname=annos_fname)
	print(list(annos))

	frames = w.get_frames( (0,10) )
	print(frames)

if __name__ == '__main__':
	fname = 'test.wiff'

	#main1(fname)
	#main2(fname)
	main3(fname)

