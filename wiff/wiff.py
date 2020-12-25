
import datetime
import os

from .db import wiffdb
from .obj import *

class WIFF:
	def __init__(self, fname):
		self.db = wiffdb(fname)
		self.db.open()

		self.recording = WIFF_recordings(self)
		self.segment = WIFF_segments(self)
		self.blob = WIFF_blobs(self)
		self.meta = WIFF_metas(self)
		self.channel = WIFF_channels(self)
		self.channelset = WIFF_channelsets(self)
		self.annotation = WIFF_annotations(self)

	@classmethod
	def open(cls, fname):
		if not os.path.exists(fname):
			raise ValueError("File not found '%s'" % fname)

		# Make object
		w = cls(fname)

		# TODO: verify basics of the database

		return w

	@classmethod
	def new(cls, fname, props):
		if os.path.exists(fname):
			raise ValueError("File already exists '%s'" % fname)

		w = cls(fname)

		# Make schema
		w.db.MakeDatabaseSchema()

		# Set pragma's
		w.db.setpragma()

		# Initialize tables
		id_r = w.db.recording.insert(start=props['start'], end=props['end'], description=props['description'], sampling=props['fs'])

		# Meta data about the recording
		w.db.meta.insert(key='WIFF.version', type='int', value='2')
		w.db.meta.insert(key='WIFF.ctime', type='datetime', value=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f"))

		# Set channels
		for c in props['channels']:
			w.db.channel.insert(id_recording=id_r, idx=c['idx'], name=c['name'], bits=c['bits'], unit=c['unit'], comment=c['comment'])
		w.db.commit()

		return w

	def add_recording(self, start, end, description, sampling, channels):
		self.db.begin()

		id_recording = self.db.recording.insert(start=start, end=end, description=description, sampling=sampling)

		for c in channels:
			self.db.channel.insert(id_recording=id_recording, idx=c['idx'], name=c['name'], bits=c['bits'], unit=c['unit'], comment=c['comment'])

		self.db.commit()

		return id_recording

	def add_segment(self, id_recording, channels, fidx_start, fidx_end, data, compression=None):
		self.db.begin()

		# Get maximum index and use next available (zero-based)
		res = self.db.segment.select('idx', '`id_recording`=?', [id_recording])
		rows = [_['idx'] for _ in res]
		if len(rows):
			idx = max(rows) + 1
		else:
			idx = 1

		# Make a channel set
		res = self.db.channelset.select('set')
		rows = [_['set'] for _ in res]
		if len(rows):
			chanset = max(rows) + 1
		else:
			chanset = 1

		# Add each channel to the set
		for c in channels:
			self.db.channelset.insert(set=chanset, id_channel=c)

		# Add data and segment
		id_blob = self.db.blob.insert(compression=compression, data=data)
		id_segment = self.db.segment.insert(id_recording=id_recording, idx=idx, fidx_start=fidx_start, fidx_end=fidx_end, channelset_id=chanset, id_blob=id_blob)

		# Make changes
		self.db.commit()

		return id_segment

	def add_annotation(self, id_recording, fidx_start, fidx_end, typ, comment, marker, data):
		self.db.begin()

		id_annotation = self.db.annotation.insert(id_recording=id_recording, fidx_start=fidx_start, fidx_end=fidx_end, type=typ, comment=comment, marker=marker, data=data)

		self.db.commit()

		return id_annotation

	def add_meta(self, id_recording, key, typ, value):
		self.db.begin()

		id_meta = self.db.meta.insert(id_recording=id_recording, key=key, type=typ, value=value)

		self.db.commit()

		return id_meta

