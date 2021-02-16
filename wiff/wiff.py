
import datetime
import os

from .db import wiffdb
from .obj import *

# 32-bit ID of the "WIFF" string generated by:
#   a = 'WIFF'.encode('ascii')
#   b = (a[0] << 24) + (a[1] << 16) + (a[2] << 8) + (a[3])
APPLICATION_ID = 1464419910

class WIFF:
	"""
	Primary interface object of this library.
	The root functions, open() and new() create instances of this class.
	All reading and manipulation of the file happens through this class.
	"""

	def __init__(self, fname):
		# Open/create the database (up to open() or new() to verify/initialize schema)
		self.db = wiffdb(fname)
		self.db.open()

		# A set of objects to make accessing easier
		self.recording = WIFF_recordings(self)
		self.segment = WIFF_segments(self)
		self.blob = WIFF_blobs(self)
		self.meta = WIFF_metas(self)
		self.channel = WIFF_channels(self)
		self.channelset = WIFF_channelsets(self)
		self.annotation = WIFF_annotations(self)

	def close(self):
		self.db.close()

	def __enter__(self):
		return self

	def __exit__(self, exc_type,exc_value,traceback):
		self.close()
		return

	def reopen_db(self):
		""" Can be a problem if accessed from a different thread. """
		self.db.reopen()

	@classmethod
	def open(cls, fname):
		"""
		Open an existing WIFF file.
		"""
		if not os.path.exists(fname):
			raise ValueError("File not found '%s'" % fname)

		# Make object
		w = cls(fname)

		# Get the application_id value
		res = w.db.execute("pragma application_id")
		row = res.fetchone()
		app_id = row[0]

		# Should match
		if app_id != APPLICATION_ID:
			raise Exception("File is a sqlite file, but application_id is wrong (%d but should be %d)" % (app_id, APPLICATION_ID))

		res = w.db.execute("select name from sqlite_master where type='table'")
		found = [_['name'] for _ in res]

		# Expected table names
		expected = [_.Name for _ in wiffdb.__schema__]

		found = set(found)
		expected = set(expected)

		absent = expected - found
		extra = found - expected

		if len(absent):
			raise Exception("WIFF file is missing tables: %s" % ','.join(absent))

		if len(extra):
			raise Exception("WIFF file contains extra tables: %s" % ','.join(extra))

		# TODO: verify column names
		# TODO: verify indexes

		return w

	@classmethod
	def new(cls, fname, props):
		"""
		Create a new WIFF file
		"""
		if os.path.exists(fname):
			raise ValueError("File already exists '%s'" % fname)

		w = cls(fname)

		# Make schema
		w.db.MakeDatabaseSchema()

		# Set pragma's
		w.db.setpragma(APPLICATION_ID)

		w.db.begin()

		# Initialize tables
		id_r = w.db.recording.insert(start=props['start'], end=props['end'], description=props['description'], sampling=props['fs'])

		# Meta data about the recording
		w.db.meta.insert(key='WIFF.version', type='int', value='2')
		w.db.meta.insert(key='WIFF.ctime', type='datetime', value=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f"))

		# Set channels
		for c in props['channels']:
			if 'storage' not in c or c['storage'] is None:
				# Pad to next full byte if partial
				q,r = divmod(c['bits'], 8)
				c['storage'] = q + (r and 1 or 0)

			w.db.channel.insert(id_recording=id_r, idx=c['idx'], name=c['name'], bits=c['bits'], storage=c['storage'], unit=c['unit'], comment=c['comment'])
		w.db.commit()

		return w

	def fidx_end(self, id_recording):
		"""
		Get the current ending frame index in a particular recording.
		If no segments are found for the recording, will return None.
		"""

		res = self.db.execute("select max(fidx_end) as fidx_end from `segment` where `id_recording`=?", (id_recording,))
		row = res.fetchone()
		if row is None:
			# No segments found
			return None
		else:
			return row['fidx_end']

	def add_recording(self, start, end, description, sampling, channels):
		"""
		Add a new recording to the file.
		Each file contains a number of recordings, recordings contain segments of data.

		@start -- start datetime object
		@end -- end datetime object
		@description -- string description of the recording
		@sampling -- samples per second of the recording
		@channels -- list of channel definitions
			'idx' -- index in the recording (1 based)
			'name' -- name of the channel
			'bits' -- number of BITS per sample
			'storage' -- number of BYTES used to store each sample, calculated from bits if not supplied
			'unit' -- string of the units the value means (eg, 'mV', 'mA')
			'comment' -- string describing the channel
		"""
		self.db.begin()

		id_recording = self.db.recording.insert(start=start, end=end, description=description, sampling=sampling)

		for c in channels:
			# Define storage by using next byte size
			if 'storage' not in c:
				# Pad to next full byte if partial
				q,r = divmod(c['bits'], 8)
				c['storage'] = q + (r and 1 or 0)

			self.db.channel.insert(id_recording=id_recording, idx=c['idx'], name=c['name'], bits=c['bits'], unit=c['unit'], comment=c['comment'], storage=c['storage'])

		self.db.commit()

		return id_recording

	def add_segment(self, id_recording, channels, fidx_start, fidx_end, id_blob):
		"""
		Add a new segment of data to a recording
		Each file contains a number of recordings, recordings contain segments of data.

		@id_recording -- recording.rowid that this segment belongs to
		@channels -- tuple/list of channel.rowid that this segment includes (order matters)
		@fidx_start -- starting frame index of the data
		@fidx_end -- ending frame index of the data
		@id_blob -- blob.rowid for the data for this segment
		"""
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
		stride = 0
		for c in channels:
			self.db.channelset.insert(set=chanset, id_channel=c)

			ch = self.db.channel.select_one('storage', '`rowid`=?', [c])
			stride += ch['storage']

		# Add data and segment
		id_segment = self.db.segment.insert(id_recording=id_recording, idx=idx, fidx_start=fidx_start, fidx_end=fidx_end, channelset_id=chanset, id_blob=id_blob, stride=stride)

		# Make changes
		self.db.commit()

		return id_segment

	def add_blob(self, data, compression=None):
		"""
		Adds a blob.

		@data -- binary data block representing all of the data
		@compression -- string indicating the compression used on the data (None if none were used)
		"""

		self.db.begin()
		id_blob = self.db.blob.insert(compression=compression, data=data)
		self.db.commit()

		return id_blob

	def add_annotation_C(self, id_recording, fidx_start, fidx_end, comment):
		"""
		Adds a comment ('C') annotation to a recording.
		"""
		return self.add_annotation(id_recording, fidx_start, fidx_end, typ='C', comment=comment, marker=None, data=None)
	def add_annotation_M(self, id_recording, fidx_start, fidx_end, marker):
		"""
		Adds a marker ('M') annotation to a recording.
		"""
		return self.add_annotation(id_recording, fidx_start, fidx_end, typ='M', comment=None, marker=marker, data=None)
	def add_annotation_D(self, id_recording, fidx_start, fidx_end, marker, data):
		"""
		Adds a data ('D') annotation to a recording.
		"""
		return self.add_annotation(id_recording, fidx_start, fidx_end, typ='D', comment=None, marker=marker, data=data)

	def add_annotation(self, id_recording, fidx_start, fidx_end, typ, comment, marker, data):
		"""
		Add an annotation to a recording.

		@id_recording -- recording.rowid this annotation is attached to
		@fidx_start -- Starting frame index of the annotation
		@fidx_end -- Ending frame index of the annotation (same as start if applying to a single frame)
		@typ -- a single letter indicating the annotation type
		@comment -- a string comment, if the annotation type supports it
		@marker -- a 4-character marker string, if the annotation type supports it
		@data -- an integer data value, if the annotation type supports it

		Annotation types:
			'C' -- Comment (marker and data not included), useful for human annotating something specific (eg, patient symptoms)
			'M' -- Marker (comment and data not included), useful for marking well-defined events (eg, QRS)
			'D' -- Marker and data value (comment not included), useful for marking well-defined events that has additional interpretive meaning (eg, QRS duration)
		"""
		self.db.begin()

		id_annotation = self.db.annotation.insert(id_recording=id_recording, fidx_start=fidx_start, fidx_end=fidx_end, type=typ, comment=comment, marker=marker, data=data)

		self.db.commit()

		return id_annotation

	def add_meta_int(self, id_recording, key, value):
		return self.add_meta(id_recording, key, 'int', str(value))

	def add_meta_str(self, id_recording, key, value):
		return self.add_meta(id_recording, key, 'str', str(value))

	def add_meta_bool(self, id_recording, key, value):
		return self.add_meta(id_recording, key, 'bool', str(int(bool(value))))

	def add_meta_datetime(self, id_recording, key, value):
		return self.add_meta(id_recording, key, 'datetime', value.strftime("%Y-%m-%d %H:%M:%S.%f"))

	def add_meta(self, id_recording, key, typ, value):
		"""
		Add a meta value to thie file (@id_recording is None) or to a recording.
		Meta values are a key/value pair with all values stored as strings and @typ indicating how to interpret the string.

		@id_recording -- recording to attach the meta value to (None means it applies to the file itself)
		@key -- string key value
		@typ -- string representing the way to interpret the @value (typically a python type)
		@value -- string value value

		Suggested types:
			'int' -- integer
			'str' -- string
			'datetime' -- datetime.datetime.strptime("%Y-%m-%d %H:%M:%S.%f") value
			'bool' -- boolean stored as integer (suggest '0' and '1' as the values)
			'blob' -- binary storage and interpreted as a blob.rowid integer value
		"""

		#  ensure key is unique to the id_recording value
		if id_recording is None:
			row = self.db.meta.select_one('rowid', '`id_recording` is null and `key`=?', [key])
		else:
			row = self.db.meta.select_one('rowid', '`id_recording`=? and `key`=?', [id_recording, key])

		if row is not None:
			raise ValueError("Cannot insert meta value with duplicate key name (key=%s, id_recording=%s, meta.rowid=%d)" % (key, id_recording, row['rowid']))

		self.db.begin()

		id_meta = self.db.meta.insert(id_recording=id_recording, key=key, type=typ, value=value)

		self.db.commit()

		return id_meta

	def find_annotations_by_fidx(self, fidx_start,fidx_end):
		if fidx_start is None and fidx_end is None:
			raise ValueError("Must supply at least start or end frame index to search")
		elif fidx_end is None:
			# start specified, so anything from that index onward
			res = self.db.annotation.select(['id','id_recording','fidx_start','fidx_end','type','comment','marker','data'], '? <= `fidx_end`', [fidx_start])

		elif fidx_start is None:
			# end specified, so anything from zero to that index
			res = self.db.annotation.select(['id_recording','fidx_start','fidx_end','type','comment','marker','data'], '`fidx_start` <= ?', [fidx_end])

		else:
			# start and end specified
			res = self.db.annotation.select(['id_recording','fidx_start','fidx_end','type','comment','marker','data'], '(`fidx_start` >= ? and ? <= `fidx_end`) or (`fidx_start` >= ? and ? <= `fidx_end`)', [fidx_start, fidx_end])

		rows = [dict(_) for _ in res]
		return rows

